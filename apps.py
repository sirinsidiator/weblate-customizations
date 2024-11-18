from django.apps import AppConfig

class CustomizeConfig(AppConfig):

    verbose_name = 'docker customize config'
    name = "customize"

    def ready(self):
        from weblate.formats.models import FormatsConf
        from django.conf import settings
        FormatsConf.EXPORTERS += ("customize.exporter.LibGetTextExporter",)
        setattr(settings, "WEBLATE_EXPORTERS", FormatsConf.EXPORTERS)
        FormatsConf.FORMATS += ("customize.exporter.LibGetTextFormat",)
        setattr(settings, "WEBLATE_FORMATS", FormatsConf.FORMATS)
        setattr(settings, "DEFAULT_ADDONS", {
            "weblate.gettext.customize": {
                "width": 77
            },
            "weblate.gettext.authors": {},
            "sirinsidiator.libgettext.updatemessages": {},
            "weblate.gettext.msgmerge": {
                "previous": True,
                "fuzzy": True
            },
            "weblate.cleanup.generic": {},
            "sirinsidiator.libgettext.generateluafiles": {},
            "sirinsidiator.libgettext.config": {},
        })