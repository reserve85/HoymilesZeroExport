from configparser import ConfigParser


class ConfigProvider:

    def update(self):
        """
        This function is called every loop cycle. You can use it to update and cache your configuration from a remote
        source.
        """
        pass

    def get_powermeter_target_point(self):
        """
        The target power for powermeter in watts
        """
        pass

    def get_powermeter_max_point(self):
        """
        The maximum power of your powermeter for the normal "regulation loop".
        If your powermeter jumps over this point, the limit will be increased instantly. it is like a "super high priority limit change".
        If you defined ON_GRID_USAGE_JUMP_TO_LIMIT_PERCENT > 0, then the limit will jump to the defined percent when reaching this point.
        """
        pass

    def on_grid_usage_jump_to_limit_percent(self):
        """
        If the powermeter jumps over the max point, the limit will be increased to this percent of the powermeter value.
        """
        pass

    def get_powermeter_tolerance(self):
        """
        The tolerance for the powermeter in watts. If the powermeter value is in the range of target_point - tolerance and target_point + tolerance, the limit will not be changed.
        """
        pass

    def get_min_wattage_in_percent(self, inverter_idx):
        """
        The minimum limit in percent, e.g. 5% of your inverter power rating.
        """
        pass

    def get_normal_wattage(self, inverter_idx):
        """
        Maximum limit in watts when battery is high (above HOY_BATTERY_THRESHOLD_NORMAL_LIMIT_IN_V)
        """
        pass

    def get_reduce_wattage(self, inverter_idx):
        """
        Maximum limit in watts when battery is low (below HOY_BATTERY_THRESHOLD_REDUCE_LIMIT_IN_V)
        """
        pass

    def get_battery_priority(self, inverter_idx):
        """
        Define priority of the inverters (possible values: 1 (high) ... 5 (low); default = 1). Same priorities are also possible.

        example 1 (default):
        inverter 1 = 1000W, priority = 1 // inverter 2 = 500W, priority = 1:
        set limit of 1100W -> inverter 1 is set to 733W and inverter 2 is set to 367W
        set limit of 300W -> inverter 1 is set to 200W and inverter 2 is set to 100W

        example 2:
        inverter 1 = 1000W, priority = 1 // inverter 2 = 500W, priority = 2:
        set limit of 1100W -> inverter 1 is set to 1000W and inverter 2 is set to 100W
        set limit of 300W -> inverter 1 is set to 300W and inverter 2 is powered off
        """
        pass


class ConfigFileConfigProvider(ConfigProvider):
    """
    This class reads the configuration from the fixed config file.
    """
    def __init__(self, config: ConfigParser):
        self.config = config

    def get_powermeter_target_point(self):
        return self.config.getint('CONTROL', 'POWERMETER_TARGET_POINT')

    def get_powermeter_max_point(self):
        return self.config.getint('CONTROL', 'POWERMETER_MAX_POINT')

    def get_powermeter_tolerance(self):
        return self.config.getint('CONTROL', 'POWERMETER_TOLERANCE')

    def on_grid_usage_jump_to_limit_percent(self):
        return self.config.getint('COMMON', 'ON_GRID_USAGE_JUMP_TO_LIMIT_PERCENT')

    def get_min_wattage_in_percent(self, inverter_idx):
        return self.config.getint('INVERTER_' + str(inverter_idx + 1), 'HOY_MIN_WATT_IN_PERCENT')

    def get_normal_wattage(self, inverter_idx):
        return self.config.getint('INVERTER_' + str(inverter_idx + 1), 'HOY_BATTERY_NORMAL_WATT')

    def get_reduce_wattage(self, inverter_idx):
        return self.config.getint('INVERTER_' + str(inverter_idx + 1), 'HOY_BATTERY_REDUCE_WATT')

    def get_battery_priority(self, inverter_idx):
        return self.config.getint('INVERTER_' + str(inverter_idx + 1), 'HOY_BATTERY_PRIORITY')
