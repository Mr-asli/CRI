# راهنمای اجرای CRI در GitHub Actions

این راهنما برای بسته نهایی CRI v1.0 است. فایل workflow آماده شده، اما تا اجرای واقعی در مخزن GitHub نتیجه‌ای تأییدشده محسوب نمی‌شود.

## ۱) بارگذاری مخزن

ZIP را در GitHub مستقیماً به‌عنوان مخزن Extract نکنید. آن را روی Codespaces، رایانه یا Termux استخراج کنید و محتویات پوشه `CRI-main/` را در ریشه مخزن خصوصی قرار دهید. ساختار ریشه باید شامل `backend/`, `dashboard/`, `docs/`, `tests/`, `scripts/`, `infra/`, `.github/`, و فایل‌های Compose باشد.

## ۲) تنظیم Repository Secrets

از مسیر `Settings` → `Secrets and variables` → `Actions` این secrets مستقل را اضافه کنید:

- `CRI_ADMIN_TOKEN` — حداقل ۳۲ بایت تصادفی.
- `APPROVAL_SIGNING_KEY` — حداقل ۳۲ بایت تصادفی و مستقل از Admin Token.
- `CRI_POSTGRES_PASSWORD` — رمز مالک دیتابیس.
- `CRI_APP_PASSWORD` — رمز مجزای نقش runtime برنامه (ترجیحاً رشته تصادفی hex برای URL connection string).
- `CRI_REDIS_PASSWORD` — رمز Redis.

از یک مقدار مشترک برای این secrets استفاده نکنید. مقادیر واقعی را commit نکنید.

## ۳) اجرای CI

در تب `Actions`، workflow با نام `CRI CI` را انتخاب و `Run workflow` را اجرا کنید. گردش‌کار شامل این jobهاست:

- `unit`: کامپایل Python، تست‌ها و پوشش حداقل ۸۵٪.
- `integration`: راه‌اندازی PostgreSQL/pgvector، Redis و OPA، اعمال migration و ارزیابی سیاست.
- `e2e`: اجرای Compose کامل شامل API، داشبورد و زیرساخت.
- `dashboard`: نصب npm، type-check، تست Vitest، build و Docker build.

## ۴) بررسی نتایج

هر job را جداگانه باز کنید. در صورت شکست، step قرمز و artifactهای log/coverage را بررسی کنید. سبز شدن یک job فقط همان بررسی‌ها را تأیید می‌کند. تست واقعی host watchdog، remote WORM audit و sandbox مستقل همچنان نیازمند میزبان و سرویس جداگانه است.

## ۵) محدودیت‌های محیط GitHub-hosted

Runner استاندارد برای اثبات gVisor/Firecracker و ایزولاسیون سطح میزبان کافی نیست. برای این موارد باید self-hosted runner اختصاصی با سخت‌افزار و مجوزهای لازم راه‌اندازی شود. هرگز Docker socket میزبان را به API/agent container متصل نکنید.
