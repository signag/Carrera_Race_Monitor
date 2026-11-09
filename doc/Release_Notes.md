# Release Notes


## V1.1.0

### Improvements

- The implementation for car detection has been improved.
<br>It now considers the fact that a simple car passage usually causes multiple sensor activation and deactivation events due to car body shape with specific parts, such as windshields reflecting in different directions.
<br>The implementation uses a parameter ```lockout_time``` to avoid multiple car detection events during a single passage. This parameter should be set to the typical time the car stays in the sensor region. Default is 0.1 (sec).
<br>To avoid early sensor deactivation signal that the car left the sensor region, a parameter ```clear_delay``` is used. A deactivation event is only considered significant if, after the specified period, a passage is not yet completed and if no car is detected by the sensor. The default value is 0.05 (sec)
- The implementation of car detection has been extended to cover also light barrier (break beam) sensors.

### New Features
- The software version is now shown in the configuration menu.

## V1.0.0

This is the initial implementation