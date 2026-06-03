# Kadai 3 Task 3 - CEP Occupancy Detection

Goal: detect whether someone is in the room using all available sensor data,
with faster response than a single CO2 threshold.

## Proposal for 3(a)

Single-sensor detection is fragile:

- CO2 reacts slowly and depends on ventilation / sensor position.
- Light can change because of sunlight, not only people.
- Temperature and humidity change slowly.

This proposal combines short-term evidence from several sensors:

- CO2 absolute level and 60-second rise
- BH1750 illumination change
- RPR0521 infrared illumination change
- SCD41 humidity / temperature change
- DPS310 air pressure change

The job computes an `occupancy_score` every 10 seconds over the latest 60
seconds.  If the score is at least `0.35`, it publishes `occupancy=1`; otherwise
it publishes `occupancy=0`.

This is more agile because a sudden light/infrared change can trigger a quick
response before CO2 has enough time to rise.

## Implementation for 3(b)

Input:

```text
i483-allsensors
```

Output:

```text
i483-fvtt
```

Output message examples:

```text
i483-sensors-s2410431-CEP-occupancy_score,0.430
i483-sensors-s2410431-CEP-occupancy,1
```

These appear in IoTDB under the instructor path, usually:

```text
root.devdb.i483.sensors.s2410431.CEP.occupancy_score
root.devdb.i483.sensors.s2410431.CEP.occupancy
```

## Setup

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_env.ps1
```

## Run

```powershell
.\run_task3.ps1
```

## Verify

Open another PowerShell window:

```powershell
.\verify_occupancy.ps1 --seconds 120
```

In Grafana, add a Time series panel for:

```text
root -> devdb -> i483 -> sensors -> s2410431 -> CEP -> occupancy
root -> devdb -> i483 -> sensors -> s2410431 -> CEP -> occupancy_score
```
