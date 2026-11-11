"""Characterization tests: the control loop's limit writes on fixed scenarios.

The JSON files in tests/baselines record what the script does today, right or
wrong. A test fails when a change alters any limit write or metric.

If the change in behaviour is intended, regenerate and review the diff:

    UPDATE_BASELINES=1 python -m pytest tests/test_replay_baselines.py
    git diff tests/baselines
"""
import json
import os
from pathlib import Path

import pytest

from harness import constant, replay, steps

BASELINES = Path(__file__).resolve().parent / 'baselines'

ONE = [1500]
FOUR = [600, 600, 900, 1200]   # 3300 W, as in issue #280

FAST_DECREASE = {'COMMON': {'ON_GRID_FEED_FAST_LIMIT_DECREASE': 'true'}}
CUT_TO_PRODUCTION = {'COMMON': {'MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER': '20'}}
NO_JUMP = {'COMMON': {'ON_GRID_USAGE_JUMP_TO_LIMIT_PERCENT': '0'}}
SUN_LIMITED = {'COMMON': {'ON_GRID_USAGE_JUMP_TO_LIMIT_PERCENT': '0'},
               'CONTROL': {'POWERMETER_MIN_POINT': '-200'}}
SUN_LIMITED_PLANT = dict(
    inverters=FOUR, load=steps((0, 500), (200, 1600), (245, 500)), sun=constant(830), duration=900)


def merged(*configs):
    result = {}
    for config in configs:
        for section, values in config.items():
            result.setdefault(section, {}).update(values)
    return result


def _battery_voltage(i, t):
    # inverter 1 is the battery inverter: normal -> reduce -> off -> back on
    if i != 1:
        return 52.0
    return steps((0, 52.0), (200, 47.5), (400, 46.0), (600, 52.0))(t)


SCENARIOS = {
    'steady_one_inverter': dict(
        inverters=ONE, load=constant(400), sun=constant(1200), duration=600),
    'load_steps_one_inverter': dict(
        inverters=ONE, load=steps((0, 300), (120, 1300), (420, 300)), sun=constant(1400), duration=900),
    'load_steps_four_inverters': dict(
        inverters=FOUR, load=steps((0, 300), (120, 1800), (420, 300)), sun=constant(2500), duration=900),
    'load_steps_four_inverters_no_jump': dict(
        inverters=FOUR, load=steps((0, 300), (120, 1800), (420, 300)), sun=constant(2500), duration=900,
        config=NO_JUMP),
    # issue #280: the sun caps production, a short load pushes the limit far
    # above it, then the load switches off
    'sun_limited_load_off': dict(config=SUN_LIMITED, **SUN_LIMITED_PLANT),
    'sun_limited_load_off_fast_decrease': dict(
        config=merged(SUN_LIMITED, FAST_DECREASE), **SUN_LIMITED_PLANT),
    'sun_limited_load_off_fast_decrease_stale_dtu': dict(
        config=merged(SUN_LIMITED, FAST_DECREASE), dtu_refresh_seconds=20, **SUN_LIMITED_PLANT),
    'sun_limited_load_off_cut_to_production': dict(
        config=merged(SUN_LIMITED, CUT_TO_PRODUCTION), **SUN_LIMITED_PLANT),
    'cloud_passing': dict(
        inverters=FOUR, load=constant(900), sun=steps((0, 2500), (200, 400), (500, 2500)), duration=900),
    'small_load_drop': dict(
        inverters=ONE, load=steps((0, 600), (200, 450)), sun=constant(1400), duration=500),
    'inverter_dropout': dict(
        inverters=FOUR, load=constant(1200), sun=constant(2500), duration=700,
        available=lambda i, t: not (i == 2 and 200 <= t < 400)),
    'limit_not_acknowledged': dict(
        inverters=FOUR, load=steps((0, 300), (120, 1800), (420, 300)), sun=constant(2500), duration=700,
        ack=lambda i, t: not (i == 3 and 100 <= t < 300)),
    'battery_inverter_voltage_sag': dict(
        inverters=[800, 800], load=constant(1000), sun=constant(1600), duration=900,
        inverter_config={2: {'HOY_BATTERY_MODE': 'true', 'HOY_BATTERY_NORMAL_WATT': 800,
                             'HOY_BATTERY_REDUCE_WATT': 300}},
        voltage=_battery_voltage),
}


@pytest.mark.parametrize('name', sorted(SCENARIOS))
def test_matches_baseline(name):
    actual = replay(**SCENARIOS[name]).as_baseline()
    path = BASELINES / (name + '.json')

    if os.environ.get('UPDATE_BASELINES'):
        BASELINES.mkdir(exist_ok=True)
        with open(path, 'w', newline='\n') as f:
            f.write(json.dumps(actual, indent=1) + '\n')
        return

    assert path.exists(), 'no baseline for %s; run with UPDATE_BASELINES=1' % name
    expected = json.loads(path.read_text())
    assert actual['writes'] == expected['writes']
    assert actual['power_status'] == expected['power_status']
    assert actual['metrics'] == expected['metrics']


def test_replay_is_deterministic():
    scenario = SCENARIOS['load_steps_four_inverters']
    assert replay(**scenario).as_baseline() == replay(**scenario).as_baseline()
