import os
import subprocess
import tempfile

from pathlib import Path

from customize.exporter import LibGetTextExporter

from django import forms
from django.core.management.utils import find_command
from django.utils.translation import gettext_lazy as _

from weblate.addons.base import BaseAddon, StoreBaseAddon
from weblate.addons.forms import BaseAddonForm
from weblate.addons.events import EVENT_PRE_COMMIT, EVENT_POST_UPDATE
from weblate.formats.base import (
    UpdateError,
)
from weblate.trans.util import (
    get_clean_env,
)
from weblate.utils.errors import report_error
from weblate.utils.render import render_template

class UpdateMessagesForm(BaseAddonForm):
    owner_name = forms.CharField(
        label=_("Copyright holder:"),
        required=True,
    )
    bugs_address = forms.CharField(
        label=_("Bugs address:"),
        initial="{{ url }}",
        required=False,
        help_text=_(
            "URL or email where translators should report issues with the untranslated strings. "
            "The weblate project url will be used if left empty"
        ),
    )
    source_folder = forms.CharField(
        label=_("Source folder:"),
        initial="./",
        required=False,
        help_text=_(
            "A relative path to the source files inside the repository. "
            "The project root will be used if left empty"
        ),
    )
    target_folder = forms.CharField(
        label=_("Path of generated lua files"),
        initial="{{ filename|dirname }}/{{ language_code }}.lua",
        required=False,
        help_text=_("If not specified, the location of the PO file will be used."),
    )

class UpdateMessagesAddon(StoreBaseAddon):
    compat = {"file_format": {"po-mono"}}
    events = (EVENT_PRE_COMMIT, EVENT_POST_UPDATE)
    name = "sirinsidiator.libgettext.updatemessages"
    verbose = _("LibGetText Update Messages")
    description = _("This add-on uses xgettext to update the template file whenever the source repository has been changed.")
    alert = "AddonScriptError"
    settings_form = UpdateMessagesForm

    @classmethod
    def can_install(cls, component, user):
        if find_command("xgettext") is None:
            return False
        return super().can_install(component, user)

    def pre_commit(self, translation, author):
        exporter = LibGetTextExporter(translation=translation)
        exporter.add_units(translation.unit_set.prefetch_full())

        template = self.instance.configuration.get("target_folder")
        if not template:
            template = "{{ filename|dirname }}/{{ language_code }}.lua"

        output = self.render_repo_filename(template, translation)
        if not output:
            return

        with open(output, "wb") as handle:
            handle.write(exporter.serialize())
        translation.addon_commit_files.append(output)

    def post_update(self, component, previous_head: str, skip_push: bool):
        project_root = component.full_path
        source_folder = self.instance.configuration.get("source_folder", "./")
        project_name = component.project.name
        owner_name = self.instance.configuration.get("owner_name", "unknown")
        bugs_address = self.instance.configuration.get("bugs_address", "{{ url }}")
        bugs_address = render_template(bugs_address, component=component)
        out_file = component.get_new_base_filename()

        try:
            self.do_extract_strings(project_root, source_folder, project_name, owner_name, bugs_address, out_file)
        except UpdateError as error:
            self.alerts.append(
                {
                    "addon": self.name,
                    "command": error.cmd,
                    "output": error.output,
                    "error": str(error),
                }
            )
            component.log_info("%s addon failed: %s", self.name, error)
        self.trigger_alerts(component)
        self.commit_and_push(component, files=[out_file], skip_push=skip_push)

    @classmethod
    def do_extract_strings(cls, project_root: str, source_folder: str, project_name: str, owner_name: str, bugs_address: str, out_file: str):
        """Wrapper around xgettext."""

        files = []
        project_root_path = Path(project_root)
        search_root_path = Path(project_root, source_folder).resolve()

        if not search_root_path.is_relative_to(project_root_path):
            raise UpdateError("validate source location", "specified source folder is not inside project root")

        for path in search_root_path.rglob('*.lua'):
            files.append(str(path.relative_to(project_root_path)))

        for path in search_root_path.rglob('*.xml'):
            files.append(str(path.relative_to(project_root_path)))

        files.sort()
        temp = tempfile.NamedTemporaryFile(mode="w", delete=False)
        temp.write("\n".join(files))
        temp.close()

        cmd = [
            "xgettext",
            "-L",
            "Lua",
            "-kgettext",
            "-cTRANSLATORS:",
            "--from-code",
            "utf-8",
            "--package-name=" + project_name,
            "--copyright-holder=" + owner_name,
            "--msgid-bugs-address=" + bugs_address,
            "-o",
            out_file,
            "-f",
            temp.name,
            "-v"
        ]

        try:
            result = subprocess.run(
                cmd,
                env=get_clean_env(),
                cwd=project_root,
                capture_output=True,
                check=True,
                text=True,
            )

            errors = []
            for line in result.stderr.splitlines():
                errors.append(line)
            if errors:
                raise UpdateError(" ".join(cmd), "\n".join(errors))
        except OSError as error:
            report_error(cause="Failed xgettext")
            raise UpdateError(" ".join(cmd), error)
        except subprocess.CalledProcessError as error:
            report_error(cause="Failed xgettext")
            raise UpdateError(" ".join(cmd), error.output + error.stderr)
        finally:
            if os.path.exists(temp.name):
                os.unlink(temp.name)