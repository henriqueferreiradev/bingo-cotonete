from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
import logging

logger = logging.getLogger(__name__)

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        logger.error(f'Social auth error - provider: {provider_id}')
        logger.error(f'Error: {error}')
        logger.error(f'Exception: {exception}')
        logger.error(f'Extra context: {extra_context}')
        return super().authentication_error(request, provider_id, error, exception, extra_context)