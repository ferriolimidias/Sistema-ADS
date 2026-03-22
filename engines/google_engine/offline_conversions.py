import logging
from datetime import datetime, timezone

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

logger = logging.getLogger(__name__)


class GoogleOfflineConnector:
    def enviar_click_conversion(
        self,
        gclid: str,
        valor: float,
        customer_id: str,
        conversion_action_id: str,
        credentials_dict: dict,
    ):
        customer_id_limpo = (customer_id or "").replace("-", "").strip()
        conversion_action_id_limpo = (conversion_action_id or "").strip()

        try:
            google_ads_config = dict(credentials_dict or {})
            use_client_customer_id = google_ads_config.pop("use_client_customer_id", None)
            if use_client_customer_id:
                google_ads_config["login_customer_id"] = str(use_client_customer_id).replace("-", "").strip()

            client = GoogleAdsClient.load_from_dict(google_ads_config)
            conversion_upload_service = client.get_service("ConversionUploadService")
            conversion_action_service = client.get_service("ConversionActionService")

            click_conversion = client.get_type("ClickConversion")
            click_conversion.conversion_action = conversion_action_service.conversion_action_path(
                customer_id_limpo,
                conversion_action_id_limpo,
            )
            click_conversion.gclid = gclid
            click_conversion.conversion_value = float(valor)
            click_conversion.currency_code = "BRL"
            click_conversion.conversion_date_time = datetime.now(timezone.utc).isoformat(
                sep=" ",
                timespec="seconds",
            )

            request = client.get_type("UploadClickConversionsRequest")
            request.customer_id = customer_id_limpo
            request.partial_failure = True
            request.conversions.append(click_conversion)

            response = conversion_upload_service.upload_click_conversions(request=request)

            if response.partial_failure_error and response.partial_failure_error.message:
                logger.warning(
                    "Google Ads retornou partial failure. customer_id=%s detalhe=%s",
                    customer_id_limpo,
                    response.partial_failure_error.message,
                )
            else:
                logger.info(
                    "Conversao offline enviada ao Google Ads com sucesso. customer_id=%s gclid=%s",
                    customer_id_limpo,
                    gclid,
                )

            return response
        except GoogleAdsException as exc:
            logger.exception(
                "Falha GoogleAdsException ao enviar conversao. customer_id=%s request_id=%s",
                customer_id_limpo,
                getattr(exc, "request_id", "desconhecido"),
            )
            return None
        except Exception:
            logger.exception(
                "Falha inesperada ao enviar conversao ao Google Ads. customer_id=%s",
                customer_id_limpo,
            )
            return None
