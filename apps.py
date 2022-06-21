from django.apps import AppConfig

class CustomizeConfig(AppConfig):

    verbose_name = 'docker customize config'
    name = "customize"

    def __init__(self, app_name, app_module):
        AppConfig.__init__(self,app_name, app_module)
        from weblate.formats.models import FormatsConf
        from django.conf import settings
        FormatsConf.EXPORTERS += ("customize.exporter.LibGetTextExporter",)
        setattr(settings, "WEBLATE_EXPORTERS", FormatsConf.EXPORTERS)
        FormatsConf.FORMATS += ("customize.exporter.LibGetTextFormat",)
        setattr(settings, "WEBLATE_FORMATS", FormatsConf.FORMATS)