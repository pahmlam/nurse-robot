# nurse-ai

Phần AI của Robot Y Tế: follow-me, phát hiện ngã/cháy, giọng nói, năng lượng, giám sát môi trường. Chạy dưới dạng node ROS1 Noetic trong container Docker trên Raspberry Pi 5 + AI HAT+ (Hailo-8L).

- Tài liệu: bắt đầu từ [spec/docs/README.md](spec/docs/README.md)
- Kế hoạch và tiến độ: [spec/AI_PLAN.md](spec/AI_PLAN.md)
- Hướng dẫn cho coding agent: [AGENTS.md](AGENTS.md)

## Bố cục

```text
nurse-ai/
├── AGENTS.md
├── spec/                      # đề xuất, kế hoạch, docs (tiếng Việt)
└── catkin_ws/src/
    ├── vendor/moving_server_msgs/   # copy từ repo nurse, không sửa
    ├── ai_msgs/               # (kế hoạch)
    └── ai/                    # (kế hoạch)
```

Repo `nurse` của nhóm (ROS navigation, firmware) nên được clone cùng cấp để tra cứu hợp đồng:

```text
Projects/
├── nurse/      # chỉ đọc, git pull để cập nhật
└── nurse-ai/   # repo này
```
