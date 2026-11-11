"""Direct tests of single functions, plus the known open bugs."""
import logging

import pytest

from harness import Plant, attach_plant, constant, load_script, replay, steps

FOUR = [600, 600, 900, 1200]


def _ready(inverters, sun=5000, **kwargs):
    hze = load_script(inverters, **kwargs)
    plant = Plant(inverters, load=constant(0), sun=constant(sun), duration=10 ** 6, write_seconds=0)
    attach_plant(hze, plant)
    assert hze.GetHoymilesAvailable()
    return hze, plant


def test_cast_to_int():
    hze = load_script()
    assert hze.CastToInt('12') == 12
    assert hze.CastToInt('12.9') == 12
    assert hze.CastToInt(-3.7) == -3
    with pytest.raises(ValueError):
        hze.CastToInt('abc')


def test_importing_the_script_does_not_start_the_loop():
    hze = load_script()
    assert callable(hze.main)


def test_min_and_max_watt_sums():
    hze, _ = _ready(FOUR)
    assert hze.GetMaxWattFromAllInverters() == 3300
    assert hze.GetMinWattFromAllInverters() == 165   # 5 % each


def test_apply_limits_clamps_to_min_and_max():
    hze, _ = _ready(FOUR)
    assert hze.ApplyLimitsToSetpoint(99999) == 3300
    assert hze.ApplyLimitsToSetpoint(-50) == 165
    assert hze.ApplyLimitsToSetpoint(1000) == 1000


def test_set_limit_splits_proportionally():
    hze, plant = _ready(FOUR)
    hze.SetLimit(1650)
    assert [w[2] for w in plant.writes] == [300, 300, 450, 600]
    assert sum(plant.limits) == 1650


def test_set_limit_below_minimum_sets_every_inverter_to_its_minimum():
    hze, plant = _ready(FOUR)
    hze.SetLimit(0)
    assert plant.limits == [30, 30, 45, 60]


def test_set_limit_skips_the_dtu_when_nothing_changed():
    hze, plant = _ready(FOUR)
    hze.SetLimit(1650)
    hze.SetLimit(1650)
    assert len(plant.writes) == 4


def test_unavailable_inverter_is_left_out():
    hze = load_script(FOUR)
    plant = Plant(FOUR, load=constant(0), sun=constant(5000), duration=10 ** 6, write_seconds=0,
                  available=lambda i, t: i != 3)
    attach_plant(hze, plant)
    assert hze.GetHoymilesAvailable()
    assert hze.GetMaxWattFromAllInverters() == 2100
    hze.SetLimit(2100)
    assert sorted(w[1] for w in plant.writes) == [0, 1, 2]


def test_cut_limit_to_production():
    hze, plant = _ready(FOUR, sun=825, config={'COMMON': {'MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER': '20'}})
    # production 825 W + 20 % of 3300 W
    assert hze.CutLimitToProduction(2700) == 825 + 660
    assert hze.CutLimitToProduction(1000) == 1000


# ------------------------------------------------------- regression tests

# issue #279
def test_small_reduction_does_not_use_slow_approximation(caplog):
    # 150 W step on a 1500 W inverter is below SLOW_APPROX_LIMIT_IN_PERCENT = 20 % (300 W)
    with caplog.at_level(logging.INFO):
        replay(inverters=[1500], load=steps((0, 600), (200, 450)), sun=constant(1400), duration=500)
    messages = [r.getMessage() for r in caplog.records]
    assert any('reduce limit based on previous limit setpoint' in m for m in messages)
    assert not any('by approximation' in m for m in messages)


def test_actual_power_falls_back_to_dtu_when_intermediate_meter_fails():
    hze, _ = _ready(FOUR, sun=830)

    class Broken(hze.Powermeter):
        def GetPowermeterWatts(self):
            raise RuntimeError('meter offline')

    hze.INTERMEDIATE_POWERMETER = Broken()
    assert hze.GetHoymilesActualPower() == hze.DTU.GetPowermeterWatts()


# issue #280
def test_fast_decrease_cuts_from_actual_output_when_limit_is_far_above_it():
    # 830 W of sun; a short 1600 W load pushes the limit to about 2500 W, then switches off at t=245
    result = replay(
        inverters=FOUR, load=steps((0, 500), (200, 1600), (245, 500)), sun=constant(830), duration=400,
        config={'COMMON': {'ON_GRID_USAGE_JUMP_TO_LIMIT_PERCENT': '0', 'ON_GRID_FEED_FAST_LIMIT_DECREASE': 'true'},
                'CONTROL': {'POWERMETER_MIN_POINT': '-200'}})
    limits = list(FOUR)
    total_at = {}
    for t, inverter, limit in result.writes:
        limits[inverter] = limit
        total_at[t] = sum(limits)
    before = [total for t, total in total_at.items() if t < 245][-1]
    assert before > 2000
    # one write pass (4 inverters, 3 s each) after the load switched off the limit is below production
    after = [total for t, total in total_at.items() if t <= 245 + 20][-1]
    assert after < 830


# ------------------------------------------------- runtime settings (MQTT)

def _with_overrides(hze):
    """Put an override provider in front of the config file, as the MQTT handler does."""
    from config_provider import ConfigProviderChain, OverridingConfigProvider
    overrides = OverridingConfigProvider()
    hze.CONFIG_PROVIDER = ConfigProviderChain([overrides, hze.CONFIG_PROVIDER])
    return overrides


def test_parse_bool_understands_mqtt_payloads():
    from config_provider import OverridingConfigProvider
    for payload in (b'true', b'1', 'on', 'YES', True):
        assert OverridingConfigProvider.parse_bool(payload) is True
    for payload in (b'false', b'0', 'off', 'No', False):
        assert OverridingConfigProvider.parse_bool(payload) is False
    with pytest.raises(ValueError):
        OverridingConfigProvider.parse_bool(b'maybe')


def test_fast_limit_decrease_can_be_switched_off_via_mqtt():
    from config_provider import OverridingConfigProvider
    overrides = OverridingConfigProvider()
    overrides.set_common_value('on_grid_feed_fast_limit_decrease', b'false')
    assert overrides.on_grid_feed_fast_limit_decrease() is False


# issue #224
def test_inverter_can_be_disabled_and_enabled_at_runtime():
    hze, plant = _ready(FOUR)
    overrides = _with_overrides(hze)

    overrides.set_inverter_value(1, 'enabled', b'false')
    assert hze.GetHoymilesAvailable()
    assert plant.power_status[-1][1:] == (1, False)
    assert hze.AVAILABLE == [True, False, True, True]
    assert hze.GetMaxWattFromAllInverters() == 2700
    hze.SetLimit(2700)
    assert 1 not in [w[1] for w in plant.writes]

    overrides.set_inverter_value(1, 'enabled', b'true')
    assert hze.GetHoymilesAvailable()
    assert plant.power_status[-1][1:] == (1, True)
    assert hze.AVAILABLE == [True, True, True, True]
    assert hze.GetMaxWattFromAllInverters() == 3300


def test_inverter_disabled_in_config_file_is_not_switched_off():
    hze = load_script(FOUR, inverter_config={2: {'ENABLED': 'false'}})
    plant = Plant(FOUR, load=constant(0), sun=constant(5000), duration=10 ** 6, write_seconds=0)
    attach_plant(hze, plant)
    assert hze.GetHoymilesAvailable()
    assert plant.power_status == []
    assert hze.AVAILABLE == [True, False, True, True]


# issue #262
def _battery_setup():
    hze = load_script([800, 800], inverter_config={2: {'HOY_BATTERY_MODE': 'true', 'HOY_BATTERY_NORMAL_WATT': 800}})
    plant = Plant([800, 800], load=constant(0), sun=constant(5000), duration=10 ** 6, write_seconds=0)
    attach_plant(hze, plant)   # the simulated inverter reports 52 V
    overrides = _with_overrides(hze)
    assert hze.GetHoymilesAvailable()
    return hze, plant, overrides


def test_external_battery_voltage_replaces_panel_voltage():
    hze, plant, overrides = _battery_setup()
    assert hze.GetCheckBattery()
    assert hze.HOY_BATTERY_GOOD_VOLTAGE[1]

    overrides.set_inverter_value(1, 'battery_voltage', b'46.0')   # below the OFF threshold of 47 V
    hze.GetCheckBattery()
    assert not hze.HOY_BATTERY_GOOD_VOLTAGE[1]
    assert plant.power_status[-1][1:] == (1, False)


def test_stale_external_battery_voltage_falls_back_to_panel_voltage(monkeypatch):
    import config_provider
    hze, plant, overrides = _battery_setup()
    overrides.set_inverter_value(1, 'battery_voltage', b'46.0')
    assert overrides.get_battery_voltage(1) == 46.0

    now = config_provider.time.time()
    monkeypatch.setattr(config_provider.time, 'time', lambda: now + 301)
    assert overrides.get_battery_voltage(1) is None
    hze.GetCheckBattery()
    assert hze.HOY_BATTERY_GOOD_VOLTAGE[1]      # 52 V from the inverter


def test_external_battery_voltage_can_be_reset():
    hze, plant, overrides = _battery_setup()
    overrides.set_inverter_value(1, 'battery_voltage', b'46.0')
    overrides.set_inverter_value(1, 'battery_voltage', None)
    assert overrides.get_battery_voltage(1) is None


# issue #207
def test_distribute_by_weight_is_proportional():
    hze = load_script()
    shares = hze.DistributeByWeight(400, {0: 570, 1: 570, 2: 570}, {0: 250, 1: 100, 2: 50})
    assert shares == {0: 250.0, 1: 100.0, 2: 50.0}


def test_distribute_by_weight_passes_surplus_to_the_others():
    hze = load_script()
    shares = hze.DistributeByWeight(900, {0: 300, 1: 570, 2: 570}, {0: 8, 1: 1, 2: 1})
    assert shares[0] == 300
    assert shares[1] == shares[2] == 300
    assert hze.DistributeByWeight(5000, {0: 300, 1: 570}, {0: 1, 1: 1}) == {0: 300, 1: 570}


def test_distribute_by_weight_without_weights_splits_evenly():
    hze = load_script()
    assert hze.DistributeByWeight(200, {0: 570, 1: 570}, {0: 0, 1: 0}) == {0: 100.0, 1: 100.0}


def test_set_limit_by_actual_power_follows_production():
    inverters = [600, 600, 600, 600]
    hze = load_script(inverters, config={'COMMON': {'DISTRIBUTE_LIMIT_BY_ACTUAL_POWER': 'true'}})
    plant = Plant(inverters, load=constant(0), sun=constant([280, 280, 60, 60]), duration=10 ** 6, write_seconds=0)
    attach_plant(hze, plant)
    assert hze.GetHoymilesAvailable()
    hze.SetLimit(480)
    # the two inverters that produce most get most of the limit; rated power would give 120 W each
    assert plant.limits[0] == plant.limits[1] > 170
    assert plant.limits[2] == plant.limits[3] < 70
    assert abs(sum(plant.limits) - 480) <= 4


def test_set_limit_by_actual_power_falls_back_when_dtu_fails():
    inverters = [600, 600]
    hze = load_script(inverters, config={'COMMON': {'DISTRIBUTE_LIMIT_BY_ACTUAL_POWER': 'true'}})
    plant = Plant(inverters, load=constant(0), sun=constant(5000), duration=10 ** 6, write_seconds=0)
    attach_plant(hze, plant)
    assert hze.GetHoymilesAvailable()

    def broken(pInverterId):
        raise RuntimeError('DTU offline')
    hze.DTU.GetACPower = broken
    hze.SetLimit(600)
    assert plant.limits == [300, 300]


# issue #250
class _FakeMqttClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload=None, qos=0, retain=False):
        self.published.append((topic, payload, retain))

    def subscribe(self, topic):
        pass

    def disconnect(self):
        pass


def _mqtt_handler(discovery_prefix='homeassistant', inverter_count=2):
    from config_provider import MqttHandler, OverridingConfigProvider
    handler = MqttHandler.__new__(MqttHandler)      # no broker connection
    OverridingConfigProvider.__init__(handler)
    handler.topic_prefix = 'zeropower'
    handler.set_topic = 'zeropower/set'
    handler.reset_topic = 'zeropower/reset'
    handler.log_level = None
    handler.discovery_prefix = discovery_prefix
    handler.inverter_count = inverter_count
    handler.sw_version = '1.107'
    handler.mqtt_client = _FakeMqttClient()
    return handler


def test_discovery_is_published_on_connect():
    import json
    handler = _mqtt_handler()
    handler.on_connect(handler.mqtt_client, None, None, 0, None)
    discovery = {t: json.loads(p) for t, p, retain in handler.mqtt_client.published if t.startswith('homeassistant/')}
    assert all(retain for t, p, retain in handler.mqtt_client.published if t.startswith('homeassistant/'))
    assert len(discovery) == 7 + 2 * 6

    target = discovery['homeassistant/number/hoymileszeroexport_zeropower/powermeter_target_point/config']
    assert target['command_topic'] == 'zeropower/set/powermeter_target_point'
    assert target['state_topic'] == 'zeropower/state/powermeter_target_point'
    assert target['availability_topic'] == 'zeropower/status'
    assert target['device']['sw_version'] == '1.107'

    enabled = discovery['homeassistant/switch/hoymileszeroexport_zeropower/inverter_1_enabled/config']
    assert enabled['command_topic'] == 'zeropower/set/inverter/1/enabled'
    assert enabled['payload_off'] == 'false'

    limit = discovery['homeassistant/sensor/hoymileszeroexport_zeropower/limit/config']
    assert 'command_topic' not in limit
    assert len({config['unique_id'] for config in discovery.values()}) == len(discovery)


def test_no_discovery_when_disabled():
    handler = _mqtt_handler(discovery_prefix=None)
    handler.on_connect(handler.mqtt_client, None, None, 0, None)
    assert [t for t, p, r in handler.mqtt_client.published] == ['zeropower/status']


def test_discovery_switch_payload_round_trip():
    handler = _mqtt_handler()

    class Message:
        topic = 'zeropower/set/inverter/1/enabled'
        payload = b'false'
    handler.on_message(None, None, Message())
    assert handler.get_inverter_enabled(1) is False
    handler.update()
    assert ('zeropower/state/inverter/1/enabled', 'false', True) in handler.mqtt_client.published


# ------------------------------------------------ inverter drops out / returns

def _battery_below_off_threshold(**plant_options):
    volt = {'v': 46.0}   # OFF threshold is 47 V
    hze = load_script([800, 800], inverter_config={2: {'HOY_BATTERY_MODE': 'true', 'HOY_BATTERY_NORMAL_WATT': 800}})
    plant = Plant([800, 800], load=constant(0), sun=constant(5000), duration=10 ** 6, write_seconds=0,
                  voltage=lambda i, t: volt['v'], **plant_options)
    attach_plant(hze, plant)
    overrides = _with_overrides(hze)
    # more passes than SET_POWERSTATUS_CNT, so the "already OFF" retry counter is exceeded
    for _ in range(15):
        hze.GetHoymilesAvailable()
        hze.GetCheckBattery()
    assert plant.power_on == [True, False]
    return hze, plant, overrides


def test_battery_inverter_is_switched_off_again_after_mqtt_disable_and_enable():
    hze, plant, overrides = _battery_below_off_threshold()
    overrides.set_inverter_value(1, 'enabled', b'false')
    hze.GetHoymilesAvailable()
    hze.GetCheckBattery()
    overrides.set_inverter_value(1, 'enabled', b'true')
    hze.GetHoymilesAvailable()
    assert plant.power_on[1]            # enabling switches it on ...
    hze.GetCheckBattery()
    assert not plant.power_on[1]        # ... but the battery is still empty
    assert not hze.HOY_BATTERY_GOOD_VOLTAGE[1]


def test_battery_inverter_is_switched_off_again_after_a_restart():
    available = {'inv1': True}
    hze, plant, _ = _battery_below_off_threshold(available=lambda i, t: i == 0 or available['inv1'])
    available['inv1'] = False
    hze.GetHoymilesAvailable()
    hze.GetCheckBattery()
    plant.power_on[1] = True            # a restarted inverter is on again
    available['inv1'] = True
    hze.GetHoymilesAvailable()
    hze.GetCheckBattery()
    assert not plant.power_on[1]


def test_limit_is_split_again_when_an_inverter_is_disabled():
    hze, plant = _ready([600, 600])
    overrides = _with_overrides(hze)
    hze.SetLimit(600)
    assert plant.limits == [300, 300]

    overrides.set_inverter_value(1, 'enabled', b'false')
    hze.GetHoymilesAvailable()
    hze.SetLimit(600)                   # same total as before, but only one inverter is left
    assert plant.limits[0] == 600


def test_limit_is_split_again_when_an_inverter_drops_out():
    available = {'inv1': True}
    hze = load_script([600, 600])
    plant = Plant([600, 600], load=constant(0), sun=constant(5000), duration=10 ** 6, write_seconds=0,
                  available=lambda i, t: i == 0 or available['inv1'])
    attach_plant(hze, plant)
    hze.GetHoymilesAvailable()
    hze.SetLimit(600)
    available['inv1'] = False
    hze.GetHoymilesAvailable()
    hze.SetLimit(600)
    assert plant.limits[0] == 600


def test_unknown_mqtt_keys_are_not_stored():
    from config_provider import OverridingConfigProvider
    overrides = OverridingConfigProvider()
    with pytest.raises(ValueError):
        overrides.set_inverter_value(0, 'foo', b'1')
    with pytest.raises(ValueError):
        overrides.set_common_value('bar', b'1')
    assert overrides.inverter_config == [{}]
    assert overrides.common_config == {}


def test_disabled_inverter_is_switched_off_again_after_a_restart():
    hze, plant = _ready(FOUR)
    overrides = _with_overrides(hze)
    overrides.set_inverter_value(1, 'enabled', b'false')
    hze.GetHoymilesAvailable()
    assert not plant.power_on[1]
    hze.GetHoymilesAvailable()
    assert len(plant.power_status) == 1     # it is off: nothing to do

    plant.power_on[1] = True                # next morning: the inverter restarted and produces again
    hze.GetHoymilesAvailable()
    assert plant.power_status[-1][1:] == (1, False)
    assert not plant.power_on[1]
    assert hze.AVAILABLE == [True, False, True, True]


# ---------------------------------------------------------------- peak delay

def test_peak_delay_starts_again_after_the_inverters_were_unreachable():
    # a peak starts at t=300, right before the inverter drops out (t=310..600). When the inverter is back the
    # powermeter is above POWERMETER_MAX_POINT at once (like every morning): the 60 seconds have to start again
    result = replay(
        inverters=[1500], load=steps((0, 300), (300, 1200)), sun=constant(5000), duration=800,
        available=lambda i, t: not 310 <= t < 600,
        config={'CONTROL': {'POWERMETER_PEAK_DELAY_IN_SECONDS': '60'}})
    after_return = [w for w in result.writes if w[0] >= 600]
    assert after_return != []
    assert after_return[0][0] >= 660


# ------------------------------------------------------------ MQTT handler

def test_update_survives_a_key_arriving_from_the_mqtt_thread():
    handler = _mqtt_handler()
    handler.set_common_value('powermeter_tolerance', b'10')
    handler.set_inverter_value(0, 'normal_watt', b'500')
    publish = handler.mqtt_client.publish

    def publish_and_receive(topic, payload=None, qos=0, retain=False):
        # stands for on_message running in the MQTT thread while update() iterates
        handler.common_config.setdefault('powermeter_target_point', -50)
        handler.inverter_config[0].setdefault('reduce_watt', 100)
        publish(topic, payload, qos, retain)

    handler.mqtt_client.publish = publish_and_receive
    handler.update()
    assert ('zeropower/state/powermeter_tolerance', 10, True) in handler.mqtt_client.published


def test_stop_publishes_offline_once():
    handler = _mqtt_handler()
    handler.stop()
    handler.stop()
    assert handler.mqtt_client.published == [('zeropower/status', 'offline', True)]
