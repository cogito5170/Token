"""Notification domain (notification). Skeleton only (CMD-GC0); see docs/domain-model.md.

앱 내 알림 저장 · 읽음 처리, 채널 설정(앱 내 · 이메일; Slack 은 나중).
"""
DOMAIN = "notification"
MVP = True
OWNED_TABLES = ('notifications', 'notification_prefs',)
