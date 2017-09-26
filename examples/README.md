# Configuration examples

This folder contains various example configuration YAML files that you can use for reference, or to help you getting started.

## Config 1 - Simple

```
dcos-perf-test-driver examples/config-1-simple.yml
```

This example is passing the values  `param1=` 1, 2, 3, ... 100 into a dummy shell script that just echoes the value. It then collects it's output into a metric `metric1`. 

The generated plot should look like this:

![config-1-plot](/examples/results/config-1_plot-metric1.png?raw=true)

## Config 2 - Two Dimentions

```
dcos-perf-test-driver examples/config-2-two-dimentions.yml
```

This example exploring two parameters, `param1=` 1, 2, 3, ... 10 and `param2=` 1, 2, 3, ... 10 and passing them into a dummy shell script that just echoes their sum. It then collects it's output into a metric `metric1` and plots a 2D plot.

The generated plot should look like this:

![config-2-plot](/examples/results/config-2_plot-metric1-mean.png?raw=true)

## Config 3 - Count and Measure

```
dcos-perf-test-driver.py examples/config-3-count-and-measure.yml
```

This example is modifying a parameter `param1=` 100, 200, 300, ... 1000 and for every value is launching a dummy shell script that generates 1000 random numbers. It then:

* Counts the occurrence of value `50` in the results into the `count1` metric
* Measures the duration between the first value `10` until the last value `60` into the `measure1` metric.

The generated plots should look like this:

![config-3-plot-1](/examples/results/config-3_plot-count1.png?raw=true)

![config-3-plot-2](/examples/results/config-3_plot-measure1.png?raw=true)
