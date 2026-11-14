# Vendored: moving_server_msgs

Byte-identical copy of the ROS team's package. **Do not edit here.**

- Source repo: `fw` (team repo, cloned as sibling `../fw`)
- Source path: `pi_ws/src/robot_system/moving_server_msgs/`
- Source commit: `5dbd522` (last commit touching the package; `fw` HEAD was `028239c`)
- Copied on: 2026-11-14

Why: AI nodes send `MoveCommand` goals (`MODE_TRACK_PERSON`) to `moving_server`, so the generated message classes must exist in this catkin workspace. ROS1 compares message md5 sums, so any drift breaks communication.

Re-sync after `git pull` in `../fw`:

```bash
diff -r ../fw/pi_ws/src/robot_system/moving_server_msgs catkin_ws/src/vendor/moving_server_msgs
# if anything other than VENDORED.md differs:
rsync -a --delete --exclude VENDORED.md \
  ../fw/pi_ws/src/robot_system/moving_server_msgs/ catkin_ws/src/vendor/moving_server_msgs/
# then update "Source commit" and "Copied on" above
```
