from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
from bot_manager.payment_service import payment_service
from bot_manager.models import Appointment
from django.utils import timezone


@csrf_exempt
def yookassa_webhook(request):
    """Обработчик webhook от YooKassa"""
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    
    # Проверяем подпись
    signature = request.headers.get('X-Yookassa-Signature')
    if not payment_service.verify_webhook(request.body.decode(), signature):
        return HttpResponse('Invalid signature', status=403)
    
    # Обрабатываем уведомление
    data = json.loads(request.body)
    
    if data['event'] == 'payment.succeeded':
        payment_id = data['object']['id']
        appointment_id = data['object']['metadata']['appointment_id']
        
        try:
            appointment = Appointment.objects.get(id=appointment_id)
            appointment.payment_status = 'paid'
            appointment.status = 'paid'
            appointment.payment_date = timezone.now()
            appointment.save()
            
            # Можно отправить уведомление в Telegram
            # send_telegram_notification(appointment)
            
        except Appointment.DoesNotExist:
            pass
    
    return HttpResponse('OK', status=200)
