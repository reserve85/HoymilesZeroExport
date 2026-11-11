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
