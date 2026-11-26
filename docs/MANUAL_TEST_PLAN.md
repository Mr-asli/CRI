# برنامه تست دستی — ۱۸ معیار پذیرش

این نسخه پیش از GitHub است. وضعیت‌ها فقط به شواهد موجود اشاره دارند؛ هیچ تستی را بدون اجرای واقعی سبز فرض نکنید.

| # | معیار | مسیر تست دستی | وضعیت فعلی |
|---:|---|---|---|
| 1 | شش ایجنت | با Bearer معتبر `GET /api/agents` و سپس `POST /api/agents/{role}/run` برای هر شش نقش را اجرا کنید. | کلاس‌ها و endpoint پایه موجود؛ چرخه LLM/worker خودکار نیست. |
| 2 | Orchestrator/DAG | تست‌های `tests/test_agents_orchestrator.py` را ببینید؛ بعد از API DAG endpoint وجود ندارد. | منطق DAG محلی تست شده؛ API/queue توزیع‌شده ندارد. |
| 3 | Policy مستقل | Rego را در OPA اجرا و اتصال runtime را بررسی کنید. | Rego artifact موجود؛ runtime هنوز in-process است. |
| 4 | جلوگیری از افزایش scope | درخواست scope خارج از نقش را از Policy و Factory امتحان کنید. | تست محلی موجود. |
| 5 | فرزند ≤ والد | از والد research فرزند developer بسازید و scope را بررسی کنید. | intersection در Factory تست شده. |
| 6 | Sandbox واقعی | در Docker Linux تست کنید؛ `docker inspect` را برای network none، read-only، non-root، cap-drop، no-new-privileges و منابع بررسی کنید. | محلی مسدود؛ Docker در دسترس نیست. |
| 7 | Fail-Closed | Docker را متوقف کنید و تلاش تست/تأیید را انجام دهید؛ باید رد شود. | مسیر عدم وجود Docker در unit test پاس شده. |
| 8 | Audit tamper detection | یک event را تغییر یا حذف کنید و `make audit` را اجرا کنید. | زنجیره محلی تست شده؛ WORM نیست. |
| 9 | Audit immutable مستقل | با نقش DB برنامه تلاش UPDATE/DELETE کنید و Object Lock را بررسی کنید. | مسدود؛ PostgreSQL/WORM متصل نیست. |
| 10 | Approval ضد Replay | توکن را مصرف و دوباره مصرف کنید؛ توکن منقضی/متعلق به proposal دیگر را نیز امتحان کنید. | HMAC/TTL/SQLite nonce در تست محلی پوشش دارد. |
| 11 | انتشار بدون approval | تلاش تصمیم بدون توکن، توکن نامعتبر و وضعیت غیر tested را انجام دهید. | گردش proposal محدود تست شده؛ version registry کامل نیست. |
| 12 | Rollback | نسخه را promote و rollback کنید. | مسدود؛ version registry/rollback engine وجود ندارد. |
| 13 | احراز هویت API | endpointهای حساس را بدون Bearer و با توکن نادرست صدا بزنید. | static bearer در تست محلی؛ JWT/session/CSRF نداریم. |
| 14 | داشبورد React | `cd dashboard && npm install && npm run lint && npm test -- --run && npm run build`؛ سپس وضعیت Overview را با `/api/status` تطبیق دهید. | shell و Overview live API نوشته شده؛ npm install محلی timeout شد؛ صفحات دیگر shell هستند. |
| 15 | حافظه پایدار و versioned | restart کنید و snapshot/restore را بررسی کنید. | مسدود؛ حافظه فعلاً in-process است. |
| 16 | Integration/CI | GitHub Actions را اجرا و healthcheck، logs و artifacts را بررسی کنید. | Workflow آماده، هنوز اجرا نشده؛ DB فقط healthcheck می‌شود. |
| 17 | مستندات همخوان | ادعاها را با `AUDIT_REPORT.md`, `STATUS.md`, تست‌ها و کد مقایسه کنید. | وضعیت‌ها و محدودیت‌ها ثبت شده؛ ممیزی نهایی هنوز باز است. |
| 18 | نصب تکرارپذیر | روی Linux تمیز `.env` بسازید و `make up/test/audit/e2e/kill/reset` را اجرا کنید. | محلی فقط test و audit پاس؛ Docker targetها هنوز اثبات نشده‌اند. |

هر موردی که وضعیت آن «مسدود»، «جزئی» یا «آماده اجرا نشده» است، معیار پذیرش تکمیل‌شده محسوب نمی‌شود.
