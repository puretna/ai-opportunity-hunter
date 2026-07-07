# AI Opportunity Hunter

Her gün AI/tech kaynaklarından terimler toplar, domain adayları üretir ve rapor oluşturur.

## Çalıştırma

```bash
pip install -r requirements.txt
python hunter.py
```

## GitHub Actions

Bu repo her gün otomatik çalışacak şekilde ayarlandı. Çıktılar:

- `reports/latest_report.md`
- `reports/domain_candidates.csv`

## Telegram opsiyonel

Telegram bildirimi için GitHub Secrets'a şunları ekleyin:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Boş bırakırsanız sadece repo içinde rapor üretir.
