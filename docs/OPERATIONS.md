# عملیات CRI — راهنمای داخلی

## پیش‌نیازها

- Linux x86_64، Python 3.11+ برای تست محلی.
- Docker Engine و Docker Compose plugin برای اجرای Compose.
- برای محیط محلی، `.env.example` را به `.env` کپی و secretهای تصادفی مستقل حداقل ۳۲ بایتی تنظیم کنید.
- `.env` واقعی را commit نکنید.

## نصب و اجرا

```sh
cp .env.example .env
# مقادیر CRI_ADMIN_TOKEN و CRI_APPROVAL_SECRET را با secretهای مستقل جایگزین کنید
make up
```

API روی `http://127.0.0.1:8000` در دسترس است. `/api/status` وضعیت عمومی را می‌دهد؛ endpointهای حساس به `Authorization: Bearer $CRI_ADMIN_TOKEN` نیاز دارند.

## تست و ممیزی

```sh
python -m pip install -e 'backend[test]'
make test
make audit
```

`make e2e` در وضعیت فعلی Compose smoke test است، نه E2E چندایجنتی کامل. `make kill` به API در حال اجرا نیاز دارد و latch نرم‌افزاری را فعال و سپس reset می‌کند. برای داده محلی می‌توانید از `scripts/backup.sh` و `scripts/restore.sh` استفاده کنید؛ restore فقط روی مسیر خالی و با `CRI_RESTORE_CONFIRM=YES` اجرا می‌شود. این اسکریپت‌ها جایگزین backup دیتابیس توزیع‌شده نیستند.

## Backup و Restore

در وضعیت فعلی داده‌های کاری process-local هستند و audit/nonce محلی در volume نگهداری می‌شوند. برای snapshot آزمایشی:

```sh
docker compose stop
mkdir -p backup
docker run --rm -v cri_cri-data:/data -v "$PWD/backup:/backup" alpine tar czf /backup/cri-data.tgz -C /data .
docker compose start
```

Restore فقط پس از توقف سرویس و بررسی نسخه backup انجام شود. فرمان destructive را روی داده اصلی بدون snapshot جداگانه اجرا نکنید. این روش backup production نیست.

## KVM، gVisor و Firecracker در آینده

بررسی KVM:

```sh
ls -l /dev/kvm
```

اگر فایل وجود ندارد یا دسترسی read/write ندارید، میزبان برای Firecracker آماده نیست. برای gVisor، بسته `runsc` را از مستندات رسمی و repository رسمی همان توزیع نصب کنید، سپس Docker runtime را طبق راهنمای رسمی gVisor پیکربندی کنید. برای Firecracker، release رسمی را دریافت، `firecracker` و `jailer` را نصب، دسترسی KVM و jail/chroot و محدودیت منابع را تنظیم کنید. هرگز این runtimeها را با خاموش‌کردن کنترل‌های میزبان یا اجرای privileged عمومی جایگزین نکنید.

برای اتصال runner: در مخزن خصوصی به `Settings → Actions → Runners → New self-hosted runner` بروید، Linux و معماری را انتخاب و دستورهای تولیدشده را روی میزبان اختصاصی اجرا کنید. runner را با label اختصاصی `cri-kvm` ثبت کنید، به مخزن خصوصی محدود نگه دارید و jobهای نیازمند KVM را فقط روی آن label زمان‌بندی کنید. توکن ثبت runner کوتاه‌عمر است و نباید در repo یا log ذخیره شود.

تا زمان فراهم شدن `/dev/kvm` و اجرای تست‌های provider، gVisor/Firecracker پشتیبانی‌شده محسوب نمی‌شوند و Fail-Closed الزامی است.
