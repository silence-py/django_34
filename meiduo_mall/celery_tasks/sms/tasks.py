from celery_tasks.main import celery_app
# from celery_tasks.sms.yuntongxun import constants
# from celery_tasks.sms.yuntongxun.sms import CCP
from meiduo_mall.libs.yuntongxun.sms import CCP
from meiduo_mall.apps.verifications import constants


@celery_app.task(name='ccp_send_sms_code')
def ccp_send_sms_code(mobile, sms_code):

    CCP().send_template_sms(mobile, [sms_code, constants.SMS_CODE_REDIS_EXPIRES // 60], 1)

