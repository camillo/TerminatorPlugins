import terminatorlib.plugin as plugin
from gtk import Label

# AVAILABLE must contain a list of all the classes that you want exposed
AVAILABLE = ['TestPlugin']

class TestPlugin(plugin.Plugin):
    capabilities = ['test']

    def do_test(self):
        return('TestPluginWin')

    class Config(plugin.PluginConfig):

        def get_config_dialog(self, config):
            ret = Label()
            ret.set_text("my test options")
            return ret 