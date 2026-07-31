import os
import json
import hashlib
import hmac
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from asgiref.sync import sync_to_async
from bot_manager.models import Appointment

# используем YooKassa

class PaymentService:
    def __init__(self):
        # Настройки для YooKassa
        self.shop_id = os.getenv('YOOKASSA_SHOP_ID')
        self.secret_key = os.getenv('YOOKASSA_SECRET_KEY')
        self.return_url = os.getenv('PAYMENT_RETURN_URL', 'https://t.me/your_bot')
        
    async def create_payment(self, appointment_id, amount, description="Оплата услуги"):
        """Создает платеж и возвращает ссылку для оплаты"""
        try:
            from yookassa import Configuration, Payment

            Configuration.account_id = self.shop_id
            Configuration.secret_key = self.secret_key
            
            # Создаем платеж
            payment = Payment.create({
                "amount": {
                    "value": str(amount),
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": self.return_url
                },
                "capture": True,
                "description": description,
                "metadata": {
                    "appointment_id": str(appointment_id)
                }
            })
            
            # Сохраняем ID платежа в базе
            appointment = await sync_to_async(Appointment.objects.get)(id=appointment_id)
            appointment.payment_id = payment.id
            appointment.payment_amount = amount
            appointment.payment_status = 'pending'
            await sync_to_async(appointment.save)()
            
            return {
                'payment_id': payment.id,
                'confirmation_url': payment.confirmation.confirmation_url,
                'status': payment.status
            }
            
        except Exception as e:
            print(f"Ошибка создания платежа: {e}")
            return None
    
    async def check_payment_status(self, payment_id):
        """Проверяет статус платежа"""
        try:
            from yookassa import Payment, Configuration
            Configuration.account_id = self.shop_id
            Configuration.secret_key = self.secret_key
            
            payment = Payment.find_one(payment_id)

            if payment.status == 'succeeded':
                # Обновляем статус в базе
                appointment = await sync_to_async(Appointment.objects.get)(payment_id=payment_id)
                appointment.payment_status = 'paid'
                appointment.status = 'paid'
                appointment.payment_date = timezone.now()
                await sync_to_async(appointment.save)()
                return {'status': 'success', 'paid': True}
            elif payment.status == 'pending':
                return {'status': 'pending', 'paid': False}
            else:
                return {'status': 'failed', 'paid': False}
                
        except Exception as e:
            print(f"Ошибка проверки платежа: {e}")
            return {'status': 'error', 'paid': False}
    
    def verify_webhook(self, request_body, signature):
        """Проверяет подпись webhook от YooKassa"""
        try:
            # Для YooKassa
            expected_signature = hmac.new(
                self.secret_key.encode('utf-8'),
                request_body.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected_signature, signature)
        except:
            return False


payment_service = PaymentService()
