# راهنمای اجرای CRI در GitHub Actions با گوشی

این نسخه پیش از اجرای GitHub است. اجرای موفق CI هنوز اثبات نشده و بعضی قابلیت‌ها عمداً ناقص/مسدود هستند.

## ۱) ساخت مخزن خصوصی

در مرورگر گوشی وارد GitHub شوید، از منوی `+` گزینه `New repository` را بزنید، نامی مثل `cri-private` انتخاب کنید، گزینه **Private** را فعال و مخزن را بسازید.

## ۲) آپلود پروژه — سه روش

**Web Upload:** ZIP را ابتدا در فایل‌منیجر گوشی Extract کنید. در مخزن `Add file` → `Upload files` را بزنید و فایل‌های استخراج‌شده را انتخاب کنید. GitHub آپلود ZIP را خودکار Extract نمی‌کند؛ ممکن است محدودیت تعداد فایل/حجم رابط وب مانع شود.

**Codespaces (پیشنهادی):** `Code` → `Codespaces` → ساخت Codespace. ZIP را در workspace آپلود کنید، در ترمینال `unzip cri-v1.0-pre-github.zip` و سپس محتویات پوشه `cri/` را به ریشه مخزن منتقل کنید. ZIP را از workspace حذف کنید.

**Termux:** `pkg install git unzip`؛ سپس مخزن خصوصی را clone کنید، ZIP را در پوشه مخزن استخراج و محتویات `cri/` را به ریشه مخزن منتقل کنید. برای Push از روش احراز هویت رسمی و امن GitHub استفاده کنید؛ توکن را در کد یا history ترمینال قرار ندهید.

## ۳) Extract و commit

ساختار باید مستقیماً در ریشه مخزن باشد: `backend/`, `dashboard/`, `docs/`, `tests/`, `scripts/`, `.github/`. پوشه `cri/` را دوباره تو در تو نکنید. فایل ZIP را commit نکنید. تغییرات را Commit و Push کنید.

## ۴) Secrets

در `Settings` → `Secrets and variables` → `Actions` → `New repository secret` این مقادیر مستقل و تصادفی را تعریف کنید:

- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `CRI_ADMIN_TOKEN` (حداقل ۳۲ بایت)
- `APPROVAL_SIGNING_KEY` (حداقل ۳۲ بایت)

`APPROVAL_SIGNING_KEY` در workflow به `CRI_APPROVAL_SECRET` نگاشت می‌شود. در نسخه فعلی `JWT_SECRET` مصرف نمی‌شود؛ JWT هنوز پیاده‌سازی نشده است و افزودن secret به‌تنهایی آن را فعال نمی‌کند. مقادیر واقعی را در `.env` یا commit قرار ندهید.

## ۵) اجرای CI

در تب `Actions` گردش‌کار `CRI Internal CI` را باز کنید، `Run workflow` را بزنید و شاخه را انتخاب کنید. برای اجرای دموی دستی `CRI Manual Docker Demo` را اجرا کنید.

## ۶) دیدن لاگ‌ها

روی اجرای workflow بزنید، job و سپس step قرمز را باز کنید. خروجی خطا و چند خط قبل از آن را بخوانید. نام jobها: lint، unit، integration، security، e2e و dashboard.

## ۷) اصلاح از مرورگر گوشی

فایل را در مخزن باز کنید، آیکون مداد را بزنید، تغییر را ذخیره و `Commit changes` را انتخاب کنید. تغییرات غیر Markdown CI را خودکار فعال می‌کنند؛ در غیر این صورت `Run workflow` را دستی بزنید.

## ۸) دریافت artifacts

پایین صفحه اجرای workflow بخش `Artifacts` را باز کنید. coverage، integration logs، e2e logs و گزارش‌های موجود را دانلود کنید. اگر job پیش از تولید فایل شکست بخورد ممکن است artifact خالی باشد.

## ۹) معنی سبز شدن

سبز بودن هر job فقط تست‌های همان job را اثبات می‌کند. Integration فعلی سلامت PostgreSQL/pgvector و Redis را بررسی می‌کند، نه اتصال آن‌ها به repositoryهای برنامه. E2E فعلی smoke test است، نه اجرای کامل DAG چندایجنتی. Dashboard job build/test shell را بررسی می‌کند، نه تکمیل ۱۱ صفحه کاربردی. تا اجرای واقعی workflow، نتیجه‌ای سبز فرض نکنید.

## ۱۰) مدیریت دقیقه‌ها

از cache pip/npm و BuildKit استفاده می‌شود؛ اجرای هم‌زمان یک branch قبلی لغو می‌شود و مسیرهای Markdown از push CI مستثنا هستند. سهمیه دقیقه رایگان به طرح و سیاست روز GitHub وابسته است؛ مقدار فعلی را در بخش Billing حساب خود بررسی کنید، نه اینکه عدد ثابت را تضمین‌شده فرض کنید.

## ۱۱) gVisor و Firecracker در آینده

برای Firecracker باید runner لینوکسی با KVM داشته باشید. روی میزبان اجرا کنید: `ls -l /dev/kvm`. gVisor/runsc و Firecracker را فقط از مستندات رسمی و مطابق نسخه توزیع نصب کنید. سپس در `Settings` → `Actions` → `Runners` یک self-hosted runner ثبت و با label اختصاصی مانند `cri-kvm` محدود کنید. تا زمانی که تست واقعی آن runner سبز نشده، این قابلیت‌ها پشتیبانی‌شده محسوب نمی‌شوند؛ Fail-Closed فعال می‌ماند.

## چه چیزهایی این نسخه در CI برایشان تلاش می‌کند؟

Docker build/Compose smoke، healthcheck سرویس‌های PostgreSQL/pgvector و Redis، FastAPI، تست‌های Python unit/security، fail-closed sandbox، audit hash chain، Policy درون‌فرایندی و داشبورد React. GitHub Actions استاندارد gVisor/Firecracker واقعی و برخی تست‌های Chaos/penetration شدید را اثبات نمی‌کند.
