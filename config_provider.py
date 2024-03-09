import logging
from configparser import ConfigParser

logger = logging.getLogger()

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


class ConfigProviderChain(ConfigProvider):
    """
    This class is a chain of config providers. It will call all the providers in the order they are given and return the
    first non-None value.

    This is useful if you want to combine multiple config sources, e.g. a config file and a MQTT topic.
    """
    def __init__(self, providers):
        self.providers = providers

    def update(self):
        for provider in self.providers:
            provider.update()

    def __getattribute__(self, name):
        if name in ['update', 'providers']:
            return object.__getattribute__(self, name)

        def method(*args, **kwargs):
            for provider in self.providers:
                f = getattr(provider, name)
                if callable(f):
                    value = f(*args, **kwargs)
                    if value is not None:
                        return value
            return None
        return method

class OverridingConfigProvider(ConfigProvider):
    """
    This class is a config provider that allows to override the config values from code.

    This can be used as a base class for config providers that allow to change the configuration
    using a push mechanism, e.g. MQTT or a REST API.
    """
    def __init__(self):
        self.common_config = {}
        self.inverter_config = []

    @staticmethod
    def cast_value(is_inverter_value, key, value):
        if is_inverter_value:
            if key in ['min_watt_in_percent', 'normal_watt', 'reduce_watt', 'battery_priority']:
                return int(value)
            else:
                logger.error(f"Unknown inverter key {key}")
        else:
            if key in ['powermeter_target_point', 'powermeter_max_point', 'powermeter_tolerance', 'on_grid_usage_jump_to_limit_percent']:
                return int(value)
            else:
                logger.error(f"Unknown common key {key}")

    def set_common_value(self, name, value):
        if value is None:
            if name in self.common_config:
                del self.common_config[name]
                logger.info(f"Unset common config value {name}")
        else:
            cast_value = self.cast_value(False, name, value)
            self.common_config[name] = cast_value
            logger.info(f"Set common config value {name} to {cast_value}")

    def set_inverter_value(self, inverter_idx: int, name: str, value):
        if value is None:
            if inverter_idx < len(self.inverter_config) and name in self.inverter_config[inverter_idx]:
                del self.inverter_config[inverter_idx][name]
                logger.info(f"Unset inverter {inverter_idx} config value {name}")
        else:
            while len(self.inverter_config) <= inverter_idx:
                self.inverter_config.append({})
            cast_value = self.cast_value(True, name, value)
            self.inverter_config[inverter_idx][name] = cast_value
            logger.info(f"Set inverter {inverter_idx} config value {name} to {cast_value}")

    def get_powermeter_target_point(self):
        return self.common_config.get('powermeter_target_point')

    def get_powermeter_max_point(self):
        return self.common_config.get('powermeter_max_point')

    def get_powermeter_tolerance(self):
        return self.common_config.get('powermeter_tolerance')

    def on_grid_usage_jump_to_limit_percent(self):
        return self.common_config.get('on_grid_usage_jump_to_limit_percent')

    def get_min_wattage_in_percent(self, inverter_idx):
        if inverter_idx >= len(self.inverter_config):
            return None
        return self.inverter_config[inverter_idx].get('min_watt_in_percent')

    def get_normal_wattage(self, inverter_idx):
        if inverter_idx >= len(self.inverter_config):
            return None
        return self.inverter_config[inverter_idx].get('normal_watt')

    def get_reduce_wattage(self, inverter_idx):
        if inverter_idx >= len(self.inverter_config):
            return None
        return self.inverter_config[inverter_idx].get('reduce_watt')

    def get_battery_priority(self, inverter_idx):
        if inverter_idx >= len(self.inverter_config):
            return None
        return self.inverter_config[inverter_idx].get('battery_priority')


class MqttConfigProvider(OverridingConfigProvider):
    """
    Config provider that subscribes to a MQTT topic and updates the configuration from the messages.
    """
    def __init__(self, mqtt_broker, mqtt_port, client_id, mqtt_username, mqtt_password, set_topic, reset_topic):
        super().__init__()
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_username = mqtt_username
        self.mqtt_password = mqtt_password
        self.set_topic = set_topic
        self.reset_topic = reset_topic
        self.target_point = None
        self.max_point = None
        self.tolerance = None
        self.on_grid_usage_jump_to_limit_percent = None
        self.min_wattage_in_percent = []
        self.normal_wattage = []
        self.reduce_wattage = []
        self.battery_priority = []

        import paho.mqtt.client as mqtt
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        if self.mqtt_username is not None:
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
        self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port)
        self.mqtt_client.loop_start()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print("Connected with result code " + str(reason_code))
        client.subscribe(f"{self.set_topic}/#")
        client.subscribe(f"{self.reset_topic}/#")

    def on_message(self, client, userdata, msg):
        try:
            self.handle_message(msg)
        except Exception as e:
            logger.error(f"Error handling message {msg.topic}: {e}")

    def handle_message(self, msg):
        if msg.topic.startswith(self.set_topic):
            topic_suffix = msg.topic[len(self.set_topic) + 1:]
            logger.info(f"Received set message for config value {topic_suffix} with payload {msg.payload}")

            def set_common_value(name):
                self.set_common_value(name, msg.payload)

            def set_inverter_value(inverter_idx, name):
                self.set_inverter_value(inverter_idx, name, msg.payload)

        elif msg.topic.startswith(self.reset_topic):
            topic_suffix = msg.topic[len(self.reset_topic) + 1:]
            logger.info(f"Received reset message for config value {topic_suffix}")

            def set_common_value(name):
                self.set_common_value(name, None)

            def set_inverter_value(inverter_idx, name):
                self.set_inverter_value(inverter_idx, name, None)
        else:
            logger.error(f"Invalid topic {msg.topic}")
            return

        if topic_suffix.startswith("inverter/"):
            inverter_topic_suffix = topic_suffix[len("inverter/"):]

            index_config_start_pos = inverter_topic_suffix.index("/")
            if index_config_start_pos == -1:
                logger.error(f"Invalid inverter config topic {msg.topic}")
                return

            inverter = int(inverter_topic_suffix[:index_config_start_pos])
            key = inverter_topic_suffix[index_config_start_pos + 1:]
            set_inverter_value(inverter, key)
        else:
            set_common_value(topic_suffix)

    def __del__(self):
        logger.info("Disconnecting MQTT client")
        self.mqtt_client.disconnect()
