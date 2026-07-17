"""
خدمة البريد الإلكتروني — إرسال رموز OTP
"""
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from app.config import settings


conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME or "",
    MAIL_PASSWORD=settings.MAIL_PASSWORD or "",
    MAIL_FROM=settings.MAIL_FROM or "",
    MAIL_PORT=587,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)


async def send_otp_email(email: str, otp: str, user_name: str = ""):
    html = f"""
    <div dir="rtl" style="font-family: 'Segoe UI', Arial, sans-serif; padding: 20px; background: #f9fafb; border-radius: 12px;">
      <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 12px; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
        <h2 style="color: #059669; text-align: center; font-size: 24px; margin-bottom: 8px;">سوى</h2>
        <p style="color: #6b7280; text-align: center; font-size: 14px; margin-bottom: 24px;">رمز التحقق لإعادة تعيين كلمة المرور</p>

        <p style="color: #374151; font-size: 15px; line-height: 1.6;">
          مرحباً{(' ' + user_name) if user_name else ''}،
        </p>
        <p style="color: #374151; font-size: 15px; line-height: 1.6;">
          للحصول على رمز إعادة تعيين كلمة المرور، استخدم الرمز التالي:
        </p>

        <div style="text-align: center; margin: 24px 0;">
          <div style="font-size: 36px; font-weight: bold; letter-spacing: 12px;
                      color: #1a1a2e; background: #d1fae5; padding: 16px 24px;
                      border-radius: 12px; display: inline-block;">
            {otp}
          </div>
        </div>

        <p style="color: #6b7280; font-size: 13px; text-align: center;">
          صالح لمدة <strong>15 دقيقة</strong> فقط
        </p>
        <p style="color: #9ca3af; font-size: 12px; text-align: center; margin-top: 24px; border-top: 1px solid #e5e7eb; padding-top: 16px;">
          إذا لم تطلب هذا الرمز، تجاهل هذه الرسالة.<br>
          فريق سوى — <a href="https://sawa.app" style="color: #059669;">sawa.app</a>
        </p>
      </div>
    </div>
    """

    message = MessageSchema(
        subject="سوى — رمز التحقق لإعادة تعيين كلمة المرور",
        recipients=[email],
        body=html,
        subtype="html",
    )

    fm = FastMail(conf)
    await fm.send_message(message)
