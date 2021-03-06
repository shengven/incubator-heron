# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
# 
#   http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
''' query_operator_unittest.py '''
# pylint: disable=too-many-lines, missing-docstring, too-many-public-methods, undefined-variable
# over 500 bad indentation errors so disable
# pylint: disable=bad-continuation
# pylint: disable=unused-argument, unused-variable
import tornado.concurrent
import tornado.gen
import tornado.testing

from mock import patch, Mock

from heron.tools.tracker.src.python.query_operators import *

class QueryOperatorTests(tornado.testing.AsyncTestCase):
  @tornado.testing.gen_test
  def test_TS_execute(self):
    ts = TS(["a", "b", "c"])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Return mocked timeline
    @tornado.gen.coroutine
    def getMetricTimelineSideEffect(*args):
      self.assertEqual((tmaster, "a", ["c"], ["b"], 40, 360), args)
      raise tornado.gen.Return({
          "starttime": 40,
          "endtime": 360,
          "component": "a",
          "timeline": {
              "c": {
                  "b": {
                      40: "1.0",
                      100: "1.0",
                      160: "1.0",
                      220: "1.0",
                      280: "1.0",
                      340: "1.0"
                  }
              }
          }
      })

    with patch("heron.tools.tracker.src.python.query_operators.getMetricsTimeline",
               side_effect=getMetricTimelineSideEffect):
      metrics = yield ts.execute(tracker, tmaster, start, end)
      self.assertEqual(1, len(metrics))
      self.assertEqual("b", metrics[0].instance)
      self.assertEqual("c", metrics[0].metricName)
      self.assertEqual("a", metrics[0].componentName)
      self.assertDictEqual({
          120: 1.0,
          180: 1.0,
          240: 1.0,
          300: 1.0
      }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_TS_execute_when_no_timeline(self):
    ts = TS(["a", "b", "c"])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # If no timeline is returned
    @tornado.gen.coroutine
    def getMetricTimelineSideEffect(*args):
      self.assertEqual((tmaster, "a", ["c"], ["b"], 40, 360), args)
      raise tornado.gen.Return({
          "message": "some_exception"
      })

    # pylint: disable=unused-variable
    with self.assertRaises(Exception):
      with patch("heron.tools.tracker.src.python.query_operators.getMetricsTimeline",
                 side_effect=getMetricTimelineSideEffect):
        metrics = yield ts.execute(tracker, tmaster, start, end)

  @tornado.testing.gen_test
  def test_TS_execute_with_multiple_instances(self):
    ts = TS(["a", "b", "c"])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # With multiple instances
    @tornado.gen.coroutine
    def getMetricTimelineSideEffect(*args):
      self.assertEqual((tmaster, "a", ["c"], [], 40, 360), args)
      raise tornado.gen.Return({
          "starttime": 40,
          "endtime": 360,
          "component": "a",
          "timeline": {
              "c": {
                  "b": {
                      40: "1.0",
                      100: "1.0",
                      # 160: "1.0", # This value is missing
                      220: "1.0",
                      280: "1.0",
                      340: "1.0"
                  },
                  "d": {
                      40: "2.0",
                      100: "2.0",
                      160: "2.0",
                      220: "2.0",
                      280: "2.0",
                      340: "2.0"
                  }
              }
          }
      })

    # pylint: disable=unused-variable
    with patch("heron.tools.tracker.src.python.query_operators.getMetricsTimeline",
               side_effect=getMetricTimelineSideEffect):
      ts = TS(["a", "*", "c"])
      metrics = yield ts.execute(tracker, tmaster, start, end)
      self.assertEqual(2, len(metrics))
      metric1 = metrics[0]
      metric2 = metrics[1]
      for metric in metrics:
        if metric.instance == "b":
          self.assertEqual("c", metric.metricName)
          self.assertEqual("a", metric.componentName)
          self.assertDictEqual({
              # 120: 1.0, # Missing value is not reported
              180: 1.0,
              240: 1.0,
              300: 1.0
          }, metric.timeline)
        elif metric.instance == "d":
          self.assertEqual("c", metric.metricName)
          self.assertEqual("a", metric.componentName)
          self.assertDictEqual({
              120: 2.0,
              180: 2.0,
              240: 2.0,
              300: 2.0
          }, metric.timeline)
        else:
          self.fail("Wrong metrics generated by TS.execute")

  @tornado.testing.gen_test
  def test_DEFAULT_execute(self):
    ts = Mock()
    default = Default([float(0), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Return mocked timeline
    @tornado.gen.coroutine
    def ts_side_effect(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
            120: 1.0,
            180: 1.0,
            240: 1.0,
            300: 1.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect

    metrics = yield default.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertEqual("instance", metrics[0].instance)
    self.assertEqual("metricName", metrics[0].metricName)
    self.assertEqual("component", metrics[0].componentName)
    self.assertDictEqual({
      120: 1.0,
      180: 1.0,
      240: 1.0,
      300: 1.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_DEFAULT_execute_when_exception(self):
    ts = Mock()
    default = Default([float(0), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # In case of exception
    @tornado.gen.coroutine
    def ts_side_effect2(*args):
      raise Exception("some_exception")
    ts.execute.side_effect = ts_side_effect2

    with self.assertRaises(Exception):
      metrics = yield default.execute(tracker, tmaster, start, end)

  @tornado.testing.gen_test
  def test_DEFAULT_execute_when_missing_value(self):
    ts = Mock()
    default = Default([float(0), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # When missing a value
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          180: 1.0,
          240: 1.0,
          300: 1.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    metrics = yield default.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertEqual("instance", metrics[0].instance)
    self.assertEqual("metricName", metrics[0].metricName)
    self.assertEqual("component", metrics[0].componentName)
    self.assertDictEqual({
      120: 0, # Missing value filled
      180: 1.0,
      240: 1.0,
      300: 1.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_DEFAULT_execute_with_multiple_ts(self):
    ts = Mock()
    default = Default([float(0), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Multiple timelines missing some values
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          # 120: 1.0, # Missing
          180: 1.0,
          240: 1.0,
          300: 1.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 2.0,
          # 180: 2.0, # Missing
          240: 2.0,
          # 300: 2.0, # Missing
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    metrics = yield default.execute(tracker, tmaster, start, end)
    self.assertEqual(2, len(metrics))
    for metric in metrics:
      if metric.instance == "instance":
        self.assertEqual("instance", metric.instance)
        self.assertEqual("metricName", metric.metricName)
        self.assertEqual("component", metric.componentName)
        self.assertDictEqual({
          120: 0, # Filled
          180: 1.0,
          240: 1.0,
          300: 1.0
        }, metric.timeline)
      elif metric.instance == "instance2":
        self.assertEqual("instance2", metric.instance)
        self.assertEqual("metricName", metric.metricName)
        self.assertEqual("component", metric.componentName)
        self.assertDictEqual({
          120: 2.0,
          180: 0, # Filled
          240: 2.0,
          300: 0 # Filled
        }, metric.timeline)
      else:
        self.fail("Wrong metrics generated by TS.execute")

  @tornado.testing.gen_test
  def test_SUM_execute(self):
    ts = Mock()
    operator = Sum([float(10), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Return mocked timeline
    @tornado.gen.coroutine
    def ts_side_effect(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 1.0,
          180: 1.0,
          240: 1.0,
          300: 1.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertDictEqual({
      120: 11.0,
      180: 11.0,
      240: 11.0,
      300: 11.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_SUM_execute_when_exception(self):
    ts = Mock()
    operator = Sum([float(10), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # In case of exception
    @tornado.gen.coroutine
    def ts_side_effect2(*args):
      raise Exception("some_exception")
    ts.execute.side_effect = ts_side_effect2

    with self.assertRaises(Exception):
      metrics = yield operator.execute(tracker, tmaster, start, end)

  @tornado.testing.gen_test
  def test_SUM_execute_when_missing_value(self):
    ts = Mock()
    operator = Sum([float(10), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # When missing a value
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          180: 1.0,
          240: 1.0,
          300: 1.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertDictEqual({
      120: 10, # Missing value filled
      180: 11.0,
      240: 11.0,
      300: 11.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_SUM_execute_with_multiple_ts(self):
    ts = Mock()
    operator = Sum([float(10), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Multiple timelines missing some values
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          # 120: 1.0, # Missing
          180: 1.0,
          240: 1.0,
          300: 1.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 2.0,
          180: 2.0,
          240: 2.0,
          300: 2.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertDictEqual({
      120: 12.0,
      180: 13.0,
      240: 13.0,
      300: 13.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_MAX_execute(self):
    ts = Mock()
    operator = Max([ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Return mocked timeline
    @tornado.gen.coroutine
    def ts_side_effect(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 1.0,
          180: 1.0,
          240: 1.0,
          300: 1.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertDictEqual({
      120: 1.0,
      180: 1.0,
      240: 1.0,
      300: 1.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_MAX_execute_when_exception(self):
    ts = Mock()
    operator = Max([ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # In case of exception
    @tornado.gen.coroutine
    def ts_side_effect2(*args):
      raise Exception("some_exception")
    ts.execute.side_effect = ts_side_effect2

    with self.assertRaises(Exception):
      metrics = yield operator.execute(tracker, tmaster, start, end)

  @tornado.testing.gen_test
  def test_MAX_execute_when_missing_values(self):
    ts = Mock()
    operator = Max([ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # When missing a value
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          180: 1.0,
          240: 1.0,
          300: 1.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertDictEqual({
      180: 1.0,
      240: 1.0,
      300: 1.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_MAX_execute_with_multiple_ts(self):
    ts = Mock()
    operator = Max([ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Multiple timelines missing some values
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          # 120: 1.0, # Missing
          180: 1.0,
          240: 3.0,
          300: 3.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 2.0,
          180: 0.0,
          240: 2.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertDictEqual({
      120: 2.0,
      180: 1.0,
      240: 3.0,
      300: 5.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_PERCENTILE_execute(self):
    ts = Mock()
    operator = Percentile([float(90), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Return mocked timeline
    @tornado.gen.coroutine
    def ts_side_effect(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 1.0,
          180: 1.0,
          240: 1.0,
          300: 1.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertDictEqual({
      120: 1.0,
      180: 1.0,
      240: 1.0,
      300: 1.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_PERCENTILE_execute_when_exception(self):
    ts = Mock()
    operator = Percentile([float(90), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # In case of exception
    @tornado.gen.coroutine
    def ts_side_effect2(*args):
      raise Exception("some_exception")
    ts.execute.side_effect = ts_side_effect2

    with self.assertRaises(Exception):
      metrics = yield operator.execute(tracker, tmaster, start, end)

  @tornado.testing.gen_test
  def test_PERCENTILE_execute_when_missing_values(self):
    ts = Mock()
    operator = Percentile([float(90), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # When missing a value
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          180: 1.0,
          240: 1.0,
          300: 1.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertDictEqual({
      180: 1.0,
      240: 1.0,
      300: 1.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_PERCENTILE_execute_with_multiple_ts(self):
    ts = Mock()
    operator = Percentile([float(90), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Multiple timelines missing some values
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 1.0,
          180: 4.0,
          240: 6.0,
          300: 3.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 2.0,
          180: 5.0,
          240: 5.0,
          300: 5.0,
        }),
        Metrics("component", "metricName", "instance3", start, end, {
          120: 4.0,
          180: 6.0,
          240: 4.0,
          300: 4.0,
        }),
        Metrics("component", "metricName", "instance4", start, end, {
          120: 3.0,
          180: 7.0,
          240: 3.0,
          300: 6.0,
        }),
        Metrics("component", "metricName", "instance5", start, end, {
          120: 5.0,
          180: 8.0,
          240: 2.0,
          300: 7.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertDictEqual({
      120: 4.0,
      180: 7.0,
      240: 5.0,
      300: 6.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_DIVIDE_execute(self):
    ts = Mock()
    operator = Divide([float(100), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Return mocked timeline
    @tornado.gen.coroutine
    def ts_side_effect(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 1.0,
          180: 2.0,
          240: 4.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertEqual("instance", metrics[0].instance)
    self.assertDictEqual({
      120: 100.0,
      180: 50.0,
      240: 25.0,
      300: 20.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_DIVIDE_execute_when_exception(self):
    ts = Mock()
    operator = Divide([float(100), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # In case of exception
    @tornado.gen.coroutine
    def ts_side_effect2(*args):
      raise Exception("some_exception")
    ts.execute.side_effect = ts_side_effect2

    with self.assertRaises(Exception):
      metrics = yield operator.execute(tracker, tmaster, start, end)

  @tornado.testing.gen_test
  def test_DIVIDE_execute_when_missing_values(self):
    ts = Mock()
    operator = Divide([float(100), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # When missing a value
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          180: 2.0,
          240: 4.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertEqual("instance", metrics[0].instance)
    self.assertDictEqual({
      180: 50.0,
      240: 25.0,
      300: 20.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_DIVIDE_execute_with_multiple_ts(self):
    ts = Mock()
    ts2 = Mock()
    operator = Divide([ts, ts2])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Multiple timelines
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 1.0,
          180: 1.0,
          240: 1.0,
          300: 1.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 2.0,
          180: 2.0,
          240: 2.0,
          300: 2.0,
        }),
        Metrics("component", "metricName", "instance3", start, end, {
          120: 3.0,
          180: 3.0,
          240: 3.0,
          300: 3.0,
        }),
        Metrics("component", "metricName", "instance4", start, end, {
          120: 4.0,
          180: 4.0,
          240: 4.0,
          300: 4.0,
        }),
        Metrics("component", "metricName", "instance5", start, end, {
          120: 5.0,
          180: 5.0,
          240: 5.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    @tornado.gen.coroutine
    def ts_side_effect4(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 2.0,
          180: 2.0,
          240: 2.0,
          300: 2.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 4.0,
          180: 4.0,
          240: 4.0,
          300: 4.0,
        }),
        Metrics("component", "metricName", "instance3", start, end, {
          120: 6.0,
          180: 6.0,
          240: 6.0,
          300: 6.0,
        }),
        Metrics("component", "metricName", "instance4", start, end, {
          120: 8.0,
          180: 8.0,
          240: 8.0,
          300: 8.0,
        }),
        Metrics("component", "metricName", "instance5", start, end, {
          120: 10.0,
          180: 10.0,
          240: 10.0,
          300: 10.0,
        })
      ])
    ts2.execute.side_effect = ts_side_effect4

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(5, len(metrics))
    for metric in metrics:
      # All should have same value - 0.5
      self.assertDictEqual({
        120: 0.5,
        180: 0.5,
        240: 0.5,
        300: 0.5
      }, metric.timeline)

  @tornado.testing.gen_test
  def test_DIVIDE_execute_with_mulitiple_ts_when_instances_do_not_match(self):
    ts = Mock()
    ts2 = Mock()
    operator = Divide([ts, ts2])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Multiple timelines
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 1.0,
          180: 1.0,
          240: 1.0,
          300: 1.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 2.0,
          180: 2.0,
          240: 2.0,
          300: 2.0,
        }),
        Metrics("component", "metricName", "instance3", start, end, {
          120: 3.0,
          180: 3.0,
          240: 3.0,
          300: 3.0,
        }),
        Metrics("component", "metricName", "instance4", start, end, {
          120: 4.0,
          180: 4.0,
          240: 4.0,
          300: 4.0,
        }),
        Metrics("component", "metricName", "instance5", start, end, {
          120: 5.0,
          180: 5.0,
          240: 5.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    # When instances do not match
    @tornado.gen.coroutine
    def ts_side_effect4(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 2.0,
          180: 2.0,
          240: 2.0,
          300: 2.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 4.0,
          180: 4.0,
          240: 4.0,
          300: 4.0,
        })
      ])
    ts2.execute.side_effect = ts_side_effect4

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(2, len(metrics))
    instances = []
    for metric in metrics:
      instances.append(metric.instance)
      self.assertDictEqual({
        120: 0.5,
        180: 0.5,
        240: 0.5,
        300: 0.5
      }, metric.timeline)
    self.assertTrue("instance" in instances and "instance2" in instances)

  @tornado.testing.gen_test
  def test_MULTIPLY_execute(self):
    ts = Mock()
    operator = Multiply([float(100), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Return mocked timeline
    @tornado.gen.coroutine
    def ts_side_effect(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 1.0,
          180: 2.0,
          240: 4.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertEqual("instance", metrics[0].instance)
    self.assertDictEqual({
      120: 100.0,
      180: 200.0,
      240: 400.0,
      300: 500.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_MULTIPLY_execute_when_exception(self):
    ts = Mock()
    operator = Multiply([float(100), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # In case of exception
    @tornado.gen.coroutine
    def ts_side_effect2(*args):
      raise Exception("some_exception")
    ts.execute.side_effect = ts_side_effect2

    with self.assertRaises(Exception):
      metrics = yield operator.execute(tracker, tmaster, start, end)

  @tornado.testing.gen_test
  def test_MULTIPLY_execute_when_missing_values(self):
    ts = Mock()
    operator = Multiply([float(100), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # When missing a value
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          180: 2.0,
          240: 4.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertEqual("instance", metrics[0].instance)
    self.assertDictEqual({
      180: 200.0,
      240: 400.0,
      300: 500.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_MULTIPLY_execute_with_multiple_ts(self):
    ts = Mock()
    ts2 = Mock()
    operator = Multiply([ts, ts2])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Multiple timelines
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 1.0,
          180: 1.0,
          240: 1.0,
          300: 1.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 2.0,
          180: 2.0,
          240: 2.0,
          300: 2.0,
        }),
        Metrics("component", "metricName", "instance3", start, end, {
          120: 3.0,
          180: 3.0,
          240: 3.0,
          300: 3.0,
        }),
        Metrics("component", "metricName", "instance4", start, end, {
          120: 4.0,
          180: 4.0,
          240: 4.0,
          300: 4.0,
        }),
        Metrics("component", "metricName", "instance5", start, end, {
          120: 5.0,
          180: 5.0,
          240: 5.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    @tornado.gen.coroutine
    def ts_side_effect4(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 2.0,
          180: 2.0,
          240: 2.0,
          300: 2.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 4.0,
          180: 4.0,
          240: 4.0,
          300: 4.0,
        }),
        Metrics("component", "metricName", "instance3", start, end, {
          120: 6.0,
          180: 6.0,
          240: 6.0,
          300: 6.0,
        }),
        Metrics("component", "metricName", "instance4", start, end, {
          120: 8.0,
          180: 8.0,
          240: 8.0,
          300: 8.0,
        }),
        Metrics("component", "metricName", "instance5", start, end, {
          120: 10.0,
          180: 10.0,
          240: 10.0,
          300: 10.0,
        })
      ])
    ts2.execute.side_effect = ts_side_effect4

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(5, len(metrics))
    for metric in metrics:
      if metric.instance == "instance":
        self.assertDictEqual({
          120: 2,
          180: 2,
          240: 2,
          300: 2
        }, metric.timeline)
      elif metric.instance == "instance2":
        self.assertDictEqual({
          120: 8,
          180: 8,
          240: 8,
          300: 8
        }, metric.timeline)
      elif metric.instance == "instance3":
        self.assertDictEqual({
          120: 18,
          180: 18,
          240: 18,
          300: 18
        }, metric.timeline)
      elif metric.instance == "instance4":
        self.assertDictEqual({
          120: 32,
          180: 32,
          240: 32,
          300: 32
        }, metric.timeline)
      elif metric.instance == "instance5":
        self.assertDictEqual({
          120: 50,
          180: 50,
          240: 50,
          300: 50
        }, metric.timeline)

  @tornado.testing.gen_test
  def test_MULTIPLY_execute_with_multiple_ts_when_instances_do_not_match(self):
    ts = Mock()
    ts2 = Mock()
    operator = Multiply([ts, ts2])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Multiple timelines
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 1.0,
          180: 1.0,
          240: 1.0,
          300: 1.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 2.0,
          180: 2.0,
          240: 2.0,
          300: 2.0,
        }),
        Metrics("component", "metricName", "instance3", start, end, {
          120: 3.0,
          180: 3.0,
          240: 3.0,
          300: 3.0,
        }),
        Metrics("component", "metricName", "instance4", start, end, {
          120: 4.0,
          180: 4.0,
          240: 4.0,
          300: 4.0,
        }),
        Metrics("component", "metricName", "instance5", start, end, {
          120: 5.0,
          180: 5.0,
          240: 5.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    # When instances do not match
    @tornado.gen.coroutine
    def ts_side_effect4(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 2.0,
          180: 2.0,
          240: 2.0,
          300: 2.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 4.0,
          180: 4.0,
          240: 4.0,
          300: 4.0,
        })
      ])
    ts2.execute.side_effect = ts_side_effect4

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(2, len(metrics))
    instances = []
    for metric in metrics:
      instances.append(metric.instance)
      if metric.instance == "instance":
        self.assertDictEqual({
          120: 2,
          180: 2,
          240: 2,
          300: 2
        }, metric.timeline)
      elif metric.instance == "instance2":
        self.assertDictEqual({
          120: 8,
          180: 8,
          240: 8,
          300: 8
        }, metric.timeline)
    self.assertTrue("instance" in instances and "instance2" in instances)

  @tornado.testing.gen_test
  def test_SUBTRACT_execute(self):
    ts = Mock()
    operator = Subtract([float(100), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Return mocked timeline
    @tornado.gen.coroutine
    def ts_side_effect(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 1.0,
          180: 2.0,
          240: 4.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertEqual("instance", metrics[0].instance)
    self.assertDictEqual({
      120: 99.0,
      180: 98.0,
      240: 96.0,
      300: 95.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_SUBTRACT_execute_when_exception(self):
    ts = Mock()
    operator = Subtract([float(100), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # In case of exception
    @tornado.gen.coroutine
    def ts_side_effect2(*args):
      raise Exception("some_exception")
    ts.execute.side_effect = ts_side_effect2

    with self.assertRaises(Exception):
      metrics = yield operator.execute(tracker, tmaster, start, end)

  @tornado.testing.gen_test
  def test_SUBTRACT_execute_when_missing_values(self):
    ts = Mock()
    operator = Subtract([float(100), ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # When missing a value
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          180: 2.0,
          240: 4.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertEqual("instance", metrics[0].instance)
    self.assertDictEqual({
      180: 98.0,
      240: 96.0,
      300: 95.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_SUBTRACT_execute_with_multiple_ts(self):
    ts = Mock()
    ts2 = Mock()
    operator = Subtract([ts, ts2])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Multiple timelines
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 1.0,
          180: 1.0,
          240: 1.0,
          300: 1.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 2.0,
          180: 2.0,
          240: 2.0,
          300: 2.0,
        }),
        Metrics("component", "metricName", "instance3", start, end, {
          120: 3.0,
          180: 3.0,
          240: 3.0,
          300: 3.0,
        }),
        Metrics("component", "metricName", "instance4", start, end, {
          120: 4.0,
          180: 4.0,
          240: 4.0,
          300: 4.0,
        }),
        Metrics("component", "metricName", "instance5", start, end, {
          120: 5.0,
          180: 5.0,
          240: 5.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    @tornado.gen.coroutine
    def ts_side_effect4(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 2.0,
          180: 2.0,
          240: 2.0,
          300: 2.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 4.0,
          180: 4.0,
          240: 4.0,
          300: 4.0,
        }),
        Metrics("component", "metricName", "instance3", start, end, {
          120: 6.0,
          180: 6.0,
          240: 6.0,
          300: 6.0,
        }),
        Metrics("component", "metricName", "instance4", start, end, {
          120: 8.0,
          180: 8.0,
          240: 8.0,
          300: 8.0,
        }),
        Metrics("component", "metricName", "instance5", start, end, {
          120: 10.0,
          180: 10.0,
          240: 10.0,
          300: 10.0,
        })
      ])
    ts2.execute.side_effect = ts_side_effect4

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(5, len(metrics))
    for metric in metrics:
      if metric.instance == "instance":
        self.assertDictEqual({
          120: -1,
          180: -1,
          240: -1,
          300: -1
        }, metric.timeline)
      elif metric.instance == "instance2":
        self.assertDictEqual({
          120: -2,
          180: -2,
          240: -2,
          300: -2
        }, metric.timeline)
      elif metric.instance == "instance3":
        self.assertDictEqual({
          120: -3,
          180: -3,
          240: -3,
          300: -3
        }, metric.timeline)
      elif metric.instance == "instance4":
        self.assertDictEqual({
          120: -4,
          180: -4,
          240: -4,
          300: -4
        }, metric.timeline)
      elif metric.instance == "instance5":
        self.assertDictEqual({
          120: -5,
          180: -5,
          240: -5,
          300: -5
        }, metric.timeline)

  @tornado.testing.gen_test
  def test_SUBTRACT_execute_with_multiple_ts_when_instances_do_not_match(self):
    ts = Mock()
    ts2 = Mock()
    operator = Subtract([ts, ts2])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Multiple timelines
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 1.0,
          180: 1.0,
          240: 1.0,
          300: 1.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 2.0,
          180: 2.0,
          240: 2.0,
          300: 2.0,
        }),
        Metrics("component", "metricName", "instance3", start, end, {
          120: 3.0,
          180: 3.0,
          240: 3.0,
          300: 3.0,
        }),
        Metrics("component", "metricName", "instance4", start, end, {
          120: 4.0,
          180: 4.0,
          240: 4.0,
          300: 4.0,
        }),
        Metrics("component", "metricName", "instance5", start, end, {
          120: 5.0,
          180: 5.0,
          240: 5.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    # When instances do not match
    @tornado.gen.coroutine
    def ts_side_effect4(*args):
      self.assertEqual((tracker, tmaster, 100, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start, end, {
          120: 2.0,
          180: 2.0,
          240: 2.0,
          300: 2.0,
        }),
        Metrics("component", "metricName", "instance2", start, end, {
          120: 4.0,
          180: 4.0,
          240: 4.0,
          300: 4.0,
        })
      ])
    ts2.execute.side_effect = ts_side_effect4

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(2, len(metrics))
    instances = []
    for metric in metrics:
      instances.append(metric.instance)
      if metric.instance == "instance":
        self.assertDictEqual({
          120: -1,
          180: -1,
          240: -1,
          300: -1
        }, metric.timeline)
      elif metric.instance == "instance2":
        self.assertDictEqual({
          120: -2,
          180: -2,
          240: -2,
          300: -2
        }, metric.timeline)
    self.assertTrue("instance" in instances and "instance2" in instances)

  @tornado.testing.gen_test
  def test_RATE_execute(self):
    ts = Mock()
    operator = Rate([ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Return mocked timeline
    @tornado.gen.coroutine
    def ts_side_effect(*args):
      self.assertEqual((tracker, tmaster, 40, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start-60, end, {
          60: 0.0,
          120: 1.0,
          180: 2.0,
          240: 4.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertEqual("instance", metrics[0].instance)
    self.assertDictEqual({
      120: 1.0,
      180: 1.0,
      240: 2.0,
      300: 1.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_RATE_execute_when_exception(self):
    ts = Mock()
    operator = Rate([ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # In case of exception
    @tornado.gen.coroutine
    def ts_side_effect2(*args):
      raise Exception("some_exception")
    ts.execute.side_effect = ts_side_effect2

    with self.assertRaises(Exception):
      metrics = yield operator.execute(tracker, tmaster, start, end)

  @tornado.testing.gen_test
  def test_RATE_execute_when_missing_values(self):
    ts = Mock()
    operator = Rate([ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # When missing a value
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 40, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start-60, end, {
          60: 0.0,
          # 120: 1.0, # Missing
          180: 2.0,
          240: 4.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(1, len(metrics))
    self.assertEqual("instance", metrics[0].instance)
    self.assertDictEqual({
      # 180: 2.0, # Won't be there since 120 is missing
      240: 2.0,
      300: 1.0
    }, metrics[0].timeline)

  @tornado.testing.gen_test
  def test_RATE_execute_with_multiple_ts(self):
    ts = Mock()
    operator = Rate([ts])
    tmaster = Mock()
    tracker = Mock()
    start = 100
    end = 300

    # Multiple timelines
    @tornado.gen.coroutine
    def ts_side_effect3(*args):
      self.assertEqual((tracker, tmaster, 40, 300), args)
      raise tornado.gen.Return([
        Metrics("component", "metricName", "instance", start-60, end, {
          60: 0.0,
          120: 1.0,
          180: 1.0,
          240: 1.0,
          300: 1.0,
        }),
        Metrics("component", "metricName", "instance2", start-60, end, {
          60: 0.0,
          120: 2.0,
          180: 2.0,
          240: 2.0,
          300: 2.0,
        }),
        Metrics("component", "metricName", "instance3", start-60, end, {
          60: 0.0,
          120: 3.0,
          180: 3.0,
          240: 3.0,
          300: 3.0,
        }),
        Metrics("component", "metricName", "instance4", start-60, end, {
          60: 0.0,
          120: 4.0,
          180: 4.0,
          240: 4.0,
          300: 4.0,
        }),
        Metrics("component", "metricName", "instance5", start-60, end, {
          60: 0.0,
          120: 5.0,
          180: 5.0,
          240: 5.0,
          300: 5.0,
        })
      ])
    ts.execute.side_effect = ts_side_effect3

    metrics = yield operator.execute(tracker, tmaster, start, end)
    self.assertEqual(5, len(metrics))
    for metric in metrics:
      if metric.instance == "instance":
        self.assertDictEqual({
          120: 1,
          180: 0,
          240: 0,
          300: 0
        }, metric.timeline)
      elif metric.instance == "instance2":
        self.assertDictEqual({
          120: 2,
          180: 0,
          240: 0,
          300: 0
        }, metric.timeline)
      elif metric.instance == "instance3":
        self.assertDictEqual({
          120: 3,
          180: 0,
          240: 0,
          300: 0
        }, metric.timeline)
      elif metric.instance == "instance4":
        self.assertDictEqual({
          120: 4,
          180: 0,
          240: 0,
          300: 0
        }, metric.timeline)
      elif metric.instance == "instance5":
        self.assertDictEqual({
          120: 5,
          180: 0,
          240: 0,
          300: 0
        }, metric.timeline)
