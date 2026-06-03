# Kadai 3 Task 3 Report

## 3(a) Proposal

The goal is to detect whether a person is in the room more quickly than using a
single sensor. CO2 is useful, but it can react slowly because the change depends
on ventilation, room size, and sensor position. Therefore, this implementation
uses several primary sensors together.

The detector observes the latest 60 seconds and updates every 10 seconds. It
combines the following evidence:

- SCD41 CO2 absolute value and short-term increase
- BH1750 illumination change
- RPR0521 infrared illumination change
- SCD41 humidity and temperature change
- DPS310 air pressure change

Each signal adds to an `occupancy_score`. If the score is `0.35` or higher, the
room is judged as occupied. This makes the reaction faster because light or
infrared changes can be detected before CO2 rises clearly.

## 3(b) Flink Implementation

The PyFlink job reads all input from:

```text
i483-allsensors
```

The input string is expected to be:

```text
topic,timestamp,value
```

The job filters this student's primary sensor topics:

```text
i483-sensors-s2410431-SCD41-co2
i483-sensors-s2410431-SCD41-temperature
i483-sensors-s2410431-SCD41-humidity
i483-sensors-s2410431-BH1750-illumination
i483-sensors-s2410431-RPR0521-infrared_illumination
i483-sensors-s2410431-DPS310-air_pressure
```

Then it applies a sliding processing-time window:

```text
window size: 60 seconds
slide:       10 seconds
```

The output is written to:

```text
i483-fvtt
```

The output format is:

```text
topic,value
```

Example output messages:

```text
i483-sensors-s2410431-CEP-occupancy_score,0.430
i483-sensors-s2410431-CEP-occupancy,1
i483-sensors-s2410431-CEP-occupancy_reason_code,3
```

In Grafana / IoTDB, the expected paths are:

```text
root.devdb.i483.sensors.s2410431.CEP.occupancy_score
root.devdb.i483.sensors.s2410431.CEP.occupancy
root.devdb.i483.sensors.s2410431.CEP.occupancy_reason_code
```

## Discussion

This method is more agile than a simple CO2 threshold because it can react to
short-term changes from multiple sensors. However, it can also be affected by
non-human events, such as sunlight changes. For that reason, the final result is
not based on one sensor alone, but on a score calculated from several sensors.

Compared with Task 1 aggregation, this task does not only summarize sensor
values. It converts multiple sensor changes into a semantic event:

```text
person is probably present / absent
```
