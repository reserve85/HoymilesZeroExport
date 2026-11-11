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


# ------------------------------------------------------------ known bugs
# These describe the correct behaviour and are expected to fail today.
# strict=True makes them fail loudly once the bug is fixed: remove the marker then.

@pytest.mark.xfail(strict=True, reason='issue #279: SLOW_APPROX_LIMIT is computed as 0 at startup')
def test_small_reduction_does_not_use_slow_approximation(caplog):
    # 150 W step on a 1500 W inverter is below SLOW_APPROX_LIMIT_IN_PERCENT = 20 % (300 W)
    with caplog.at_level(logging.INFO):
        replay(inverters=[1500], load=steps((0, 600), (200, 450)), sun=constant(1400), duration=500)
    messages = [r.getMessage() for r in caplog.records]
    assert any('reduce limit based on previous limit setpoint' in m for m in messages)
    assert not any('by approximation' in m for m in messages)


@pytest.mark.xfail(strict=True, reason='fallback path in GetHoymilesActualPower does not return the DTU value')
def test_actual_power_falls_back_to_dtu_when_intermediate_meter_fails():
    hze, _ = _ready(FOUR, sun=830)

    class Broken(hze.Powermeter):
        def GetPowermeterWatts(self):
            raise RuntimeError('meter offline')

    hze.INTERMEDIATE_POWERMETER = Broken()
    assert hze.GetHoymilesActualPower() == hze.DTU.GetPowermeterWatts()
