"""Replay harness for HoymilesZeroExport.

Loads the real script as a module, replaces the DTU, the powermeter and the
clock with a small plant simulation, and runs the unmodified control loop
against a load / sun profile. Nothing touches the network and no real time
passes.

Typical use:

    result = replay(
        inverters=[600, 600, 900, 1200],
        load=steps((0, 1600), (300, 500)),
        sun=constant(830),
        duration=900,
        config={'COMMON': {'ON_GRID_FEED_FAST_LIMIT_DECREASE': 'true'}},
    )
    result.metrics()   # feed-in Wh, limit writes, ...
"""
import importlib.util
import itertools
import os
import sys
import tempfile
from configparser import ConfigParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'HoymilesZeroExport.py'

# Control-relevant settings are pinned here so that baselines do not move when
# somebody edits the defaults in HoymilesZeroExport_Config.ini.
PINNED_CONFIG = {
    'SELECT_DTU': {'USE_AHOY': 'false', 'USE_OPENDTU': 'false', 'USE_DEBUG': 'true'},
    'SELECT_POWERMETER': {'USE_DEBUG_READER': 'true'},
    'COMMON': {
        'ENABLE_LOG_TO_FILE': 'false',
        'SLOW_APPROX_LIMIT_IN_PERCENT': '20',
        'SLOW_APPROX_FACTOR_IN_PERCENT': '20',
        'LOOP_INTERVAL_IN_SECONDS': '20',
        'POLL_INTERVAL_IN_SECONDS': '1',
        'SET_LIMIT_TIMEOUT_SECONDS': '10',
        'ON_GRID_USAGE_JUMP_TO_LIMIT_PERCENT': '100',
        'ON_GRID_FEED_FAST_LIMIT_DECREASE': 'false',
        'MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER': '100',
        'SET_POWERSTATUS_CNT': '10',
        'SET_POWER_STATUS_DELAY_IN_SECONDS': '10',
        'LOG_TEMPERATURE': 'false',
        'SET_INVERTER_TO_MIN_ON_POWERMETER_ERROR': 'false',
    },
    'CONTROL': {
        'POWERMETER_TARGET_POINT': '-75',
        'POWERMETER_TOLERANCE': '25',
        'POWERMETER_MAX_POINT': '0',
        'POWERMETER_MIN_POINT': '-600',
        'POWERMETER_PEAK_DELAY_IN_SECONDS': '0',
    },
}

PINNED_INVERTER = {
    'ENABLED': 'true',
    'HOY_INVERTER_WATT': '',
    'HOY_MIN_WATT_IN_PERCENT': '5',
    'HOY_COMPENSATE_WATT_FACTOR': '1',
    'HOY_BATTERY_MODE': 'false',
    'HOY_BATTERY_THRESHOLD_OFF_LIMIT_IN_V': '47',
    'HOY_BATTERY_THRESHOLD_REDUCE_LIMIT_IN_V': '48',
    'HOY_BATTERY_THRESHOLD_NORMAL_LIMIT_IN_V': '48.5',
    'HOY_BATTERY_THRESHOLD_ON_LIMIT_IN_V': '51',
    'HOY_BATTERY_NORMAL_WATT': '1500',
    'HOY_BATTERY_REDUCE_WATT': '300',
    'HOY_BATTERY_IGNORE_PANELS': '',
    'HOY_BATTERY_PRIORITY': '1',
    'HOY_BATTERY_AVERAGE_CNT': '1',
}

_module_counter = itertools.count()


class ReplayFinished(BaseException):
    """Raised by the fake clock when the profile is over.

    Derives from BaseException so the script's `except Exception` handlers in
    the main loop do not swallow it.
    """


# ---------------------------------------------------------------- profiles

def constant(value):
    return lambda t: value


def steps(*points):
    """steps((0, 300), (120, 1800)) -> 300 W until t=120 s, then 1800 W."""
    points = sorted(points)

    def profile(t):
        value = points[0][1]
        for start, v in points:
            if t >= start:
                value = v
        return value
    return profile


# ------------------------------------------------------------------- plant

class Plant:
    """House, sun and inverters. All times in seconds, all powers in Watt."""

    def __init__(self, max_watts, load, sun, duration, write_seconds=3,
                 dtu_refresh_seconds=0, available=None, voltage=None, ack=None):
        self.max_watts = list(max_watts)
        self.load = load
        self.sun = sun
        self.duration = duration
        self.write_seconds = write_seconds
        self.dtu_refresh_seconds = dtu_refresh_seconds
        self.available = available or (lambda i, t: True)
        self.voltage = voltage or (lambda i, t: 52.0)
        self.ack = ack or (lambda i, t: True)

        self.t = 0.0
        self.limits = list(self.max_watts)      # inverters start unlimited
        self.power_on = [True] * len(self.max_watts)
        self.writes = []                        # (t, inverter, limit)
        self.power_status = []                  # (t, inverter, active)
        self.grid_trace = []                    # (t, grid watts), one per step
        self._reported = None
        self._reported_at = None

    def production(self, i):
        if not self.power_on[i] or not self.available(i, self.t):
            return 0.0
        share = self.sun(self.t) * self.max_watts[i] / sum(self.max_watts)
        return max(0.0, min(self.limits[i], share))

    def grid(self):
        """Positive = import from grid, negative = feed-in."""
        return self.load(self.t) - sum(self.production(i) for i in range(len(self.max_watts)))

    def reported_production(self, i):
        """What the DTU reports; may lag behind by dtu_refresh_seconds."""
        if (self._reported is None or self.dtu_refresh_seconds <= 0
                or self.t - self._reported_at >= self.dtu_refresh_seconds):
            self._reported = [self.production(k) for k in range(len(self.max_watts))]
            self._reported_at = self.t
        return self._reported[i]

    def advance(self, seconds):
        remaining = float(seconds)
        while remaining > 0:
            if self.t >= self.duration:
                raise ReplayFinished()
            dt = min(1.0, remaining)
            self.grid_trace.append((self.t, self.grid(), dt))
            self.t += dt
            remaining -= dt
        if self.t >= self.duration:
            raise ReplayFinished()


class FakeTime:
    def __init__(self, plant):
        self._plant = plant

    def sleep(self, seconds):
        self._plant.advance(seconds)

    def time(self):
        return self._plant.t


def _make_fakes(hze, plant):
    # the script rebinds the name DTU to the instance it created, so the base
    # class has to be looked up through that instance
    dtu_base = next(c for c in type(hze.DTU).__mro__ if c.__name__ == 'DTU')

    class FakeDTU(dtu_base):
        def GetACPower(self, pInverterId):
            return hze.CastToInt(plant.reported_production(pInverterId))

        def CheckMinVersion(self):
            return

        def GetAvailable(self, pInverterId):
            return plant.available(pInverterId, plant.t)

        def GetActualLimitInW(self, pInverterId):
            return plant.limits[pInverterId]

        def GetInfo(self, pInverterId):
            hze.NAME[pInverterId] = 'inv%d' % pInverterId
            hze.SERIAL_NUMBER[pInverterId] = str(pInverterId)

        def GetTemperature(self, pInverterId):
            hze.TEMPERATURE[pInverterId] = '0 degC'

        def GetPanelMinVoltage(self, pInverterId):
            return plant.voltage(pInverterId, plant.t)

        def WaitForAck(self, pInverterId, pTimeoutInS):
            if plant.ack(pInverterId, plant.t):
                return True
            plant.advance(pTimeoutInS)
            return False

        def SetLimit(self, pInverterId, pLimit):
            plant.writes.append((plant.t, pInverterId, hze.CastToInt(pLimit)))
            hze.CURRENT_LIMIT[pInverterId] = pLimit
            plant.advance(plant.write_seconds)
            plant.limits[pInverterId] = pLimit

        def SetPowerStatus(self, pInverterId, pActive):
            plant.power_status.append((plant.t, pInverterId, bool(pActive)))
            plant.power_on[pInverterId] = bool(pActive)

    class FakePowermeter(hze.Powermeter):
        def GetPowermeterWatts(self):
            return hze.CastToInt(plant.grid())

    return FakeDTU(len(plant.max_watts)), FakePowermeter()


# ------------------------------------------------------------------ loader

def _write_overlay(inverters, config, inverter_config):
    overlay = ConfigParser()
    overlay.optionxform = str
    for section, values in PINNED_CONFIG.items():
        overlay[section] = dict(values)
    overlay['COMMON']['INVERTER_COUNT'] = str(len(inverters))
    for n, watts in enumerate(inverters, start=1):
        section = dict(PINNED_INVERTER)
        section['HOY_MAX_WATT'] = str(watts)
        section.update({k: str(v) for k, v in (inverter_config or {}).get(n, {}).items()})
        overlay['INVERTER_%d' % n] = section
    for section, values in (config or {}).items():
        if not overlay.has_section(section):
            overlay.add_section(section)
        for key, value in values.items():
            overlay[section][key] = str(value)
    fd, path = tempfile.mkstemp(suffix='.ini', prefix='hze_test_')
    with os.fdopen(fd, 'w') as f:
        overlay.write(f)
    return path


def load_script(inverters=(1500,), config=None, inverter_config=None):
    """Import a fresh copy of the script with a test configuration.

    The script reads its config and builds DTU/powermeter objects at import
    time, so every call returns an independent module with clean state.
    """
    overlay = _write_overlay(inverters, config, inverter_config)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    name = 'hze_under_test_%d' % next(_module_counter)
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv
    sys.argv = [str(SCRIPT), '-c', overlay]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old_argv
        os.unlink(overlay)
    return module


def attach_plant(hze, plant):
    dtu, powermeter = _make_fakes(hze, plant)
    hze.DTU = dtu
    hze.POWERMETER = powermeter
    hze.INTERMEDIATE_POWERMETER = dtu
    hze.time = FakeTime(plant)
    return dtu, powermeter


# ------------------------------------------------------------------ result

class Result:
    def __init__(self, hze, plant):
        self.hze = hze
        self.plant = plant

    @property
    def writes(self):
        return [[round(t, 1), i, limit] for t, i, limit in self.plant.writes]

    def metrics(self, feed_in_threshold=-150):
        feed_in_ws = sum(-g * dt for _, g, dt in self.plant.grid_trace if g < 0)
        import_ws = sum(g * dt for _, g, dt in self.plant.grid_trace if g > 0)
        below = sum(dt for _, g, dt in self.plant.grid_trace if g < feed_in_threshold)
        return {
            'feed_in_wh': round(feed_in_ws / 3600, 2),
            'import_wh': round(import_ws / 3600, 2),
            'seconds_below_%dW' % abs(feed_in_threshold): round(below, 1),
            'limit_writes': len(self.plant.writes),
            'power_status_writes': len(self.plant.power_status),
        }

    def as_baseline(self):
        return {
            'metrics': self.metrics(),
            'writes': self.writes,
            'power_status': [[round(t, 1), i, a] for t, i, a in self.plant.power_status],
        }


def replay(inverters, load, sun, duration, config=None, inverter_config=None, **plant_options):
    """Run the script's main() against a simulated plant until `duration`."""
    hze = load_script(inverters, config, inverter_config)
    plant = Plant(inverters, load, sun, duration, **plant_options)
    attach_plant(hze, plant)
    try:
        hze.main()
    except ReplayFinished:
        pass
    return Result(hze, plant)
