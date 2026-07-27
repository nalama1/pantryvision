"""
check-expiring-products Lambda handler.

Triggered daily by an Amazon EventBridge rule. Scans the pantryvision-products
DynamoDB table, classifies products as expiring soon or expired, and sends a
single consolidated Amazon SES alert email when needed.
"""

import html
import logging
import os
import time
from datetime import date, datetime
from typing import TypedDict

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Created at module load time (not inside the handler) so warm-start
# invocations reuse the same SES client/connection pool instead of paying
# the setup cost on every invocation. The DynamoDB Table resource cannot be
# created here because it depends on TABLE_NAME, which is only known after
# get_alert_config() validates the environment inside the handler.
_dynamodb_resource = boto3.resource("dynamodb")
_ses_client = boto3.client("ses")

EXPIRING_WINDOW_DAYS = 7

# Lambda invocations for this feature have a small, fixed time budget (the
# overall run must classify+email within minutes, per Requirement 2.2), so
# retries are capped at 3 total attempts rather than an unbounded/longer
# backoff strategy that could eat into that budget.
MAX_SCAN_ATTEMPTS = 3
SCAN_RETRY_DELAY_SECONDS = 1


class AlertConfig(TypedDict):
    sender_address: str
    recipient_address: str
    table_name: str


class ClassifiedProduct(TypedDict):
    product_name: str
    expiration_date: str
    classification: str  # "Expiring_Product" | "Expired_Product"


AlertBatch = list[ClassifiedProduct]


class DeliveryResult(TypedDict):
    status: str  # "sent" | "not-needed" | "failed"
    failure_reason: str | None


class ConfigurationError(Exception):
    """Raised when a required environment variable is missing or blank."""


class ScanFailedError(Exception):
    """Raised when the Products_Table scan fails after exhausting retries."""


def get_alert_config() -> AlertConfig:
    """Reads ALERT_SENDER_EMAIL / ALERT_RECIPIENT_EMAIL / TABLE_NAME from env.

    Raises ConfigurationError if sender, recipient, or table name is
    missing/blank. Validating here, before any AWS call is made, lets the
    Lambda fail fast and avoid a wasted DynamoDB scan when misconfigured.
    """
    sender_address = os.environ.get("ALERT_SENDER_EMAIL")
    recipient_address = os.environ.get("ALERT_RECIPIENT_EMAIL")
    table_name = os.environ.get("TABLE_NAME")

    # Check by variable name only; never log the actual value, which could
    # be a real email address (PII) or other sensitive configuration.
    if _is_blank(sender_address):
        raise ConfigurationError("ALERT_SENDER_EMAIL is missing or blank")
    if _is_blank(recipient_address):
        raise ConfigurationError("ALERT_RECIPIENT_EMAIL is missing or blank")
    if _is_blank(table_name):
        raise ConfigurationError("TABLE_NAME is missing or blank")

    return AlertConfig(
        sender_address=sender_address,
        recipient_address=recipient_address,
        table_name=table_name,
    )


def _is_blank(value: str | None) -> bool:
    """Treats None and whitespace-only strings as blank/missing."""
    return value is None or value.strip() == ""


def scan_products(table) -> list[dict]:
    """Scans the Products_Table across all pages. Retries up to 3 total
    attempts on transient DynamoDB errors, with a short backoff between
    attempts. Raises ScanFailedError after exhausting retries.

    Retries wrap the whole pagination loop: if a page fails partway through,
    the entire scan restarts from the beginning on the next attempt, which
    keeps the retry logic simple (no partial-page bookkeeping) and is
    acceptable given the table sizes this MVP targets (Requirement 4.3).
    """
    last_error: ClientError | None = None

    for attempt in range(1, MAX_SCAN_ATTEMPTS + 1):
        try:
            items: list[dict] = []
            response = table.scan()
            items.extend(response.get("Items", []))

            while "LastEvaluatedKey" in response:
                response = table.scan(
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                items.extend(response.get("Items", []))

            return items
        except ClientError as error:
            last_error = error
            error_code = error.response.get("Error", {}).get("Code", "Unknown")
            logger.warning(
                "scan_attempt_failed=%s attempt=%s of %s",
                error_code,
                attempt,
                MAX_SCAN_ATTEMPTS,
            )
            if attempt < MAX_SCAN_ATTEMPTS:
                # Kept intentionally simple (fixed short delay rather than
                # full exponential backoff) given the Lambda's overall
                # execution time budget for this feature.
                time.sleep(SCAN_RETRY_DELAY_SECONDS)

    raise ScanFailedError(
        "Products_Table scan failed after "
        f"{MAX_SCAN_ATTEMPTS} attempts"
    ) from last_error


def classify_products(products: list[dict], current_date: date) -> AlertBatch:
    """
    Pure function: classifies each product record as Expiring_Product,
    Expired_Product, or excluded (missing expirationDate). Returns an
    AlertBatch (list of classified entries). No I/O - fully unit/property
    testable in isolation.
    """
    alert_batch: AlertBatch = []

    for product in products:
        raw_expiration = product.get("expirationDate")

        # Requirement 1.5: products without an expirationDate are excluded
        # entirely rather than raising an error, so one incomplete record
        # never blocks classification of the rest of the inventory.
        if not raw_expiration:
            continue

        expiration_date = datetime.strptime(raw_expiration, "%Y-%m-%d").date()
        days_until_expiration = (expiration_date - current_date).days

        # Upper bound is inclusive (<=7, not <7) because Requirement 1.3
        # defines the window as "on or between" current_date and
        # current_date + 7 days, i.e. a full week of advance warning.
        if 0 <= days_until_expiration <= EXPIRING_WINDOW_DAYS:
            classification = "Expiring_Product"
        elif days_until_expiration < 0:
            classification = "Expired_Product"
        else:
            # Beyond the expiring window and not yet expired: not alert-worthy.
            continue

        alert_batch.append(
            ClassifiedProduct(
                product_name=product.get("productName", ""),
                expiration_date=raw_expiration,
                classification=classification,
            )
        )

    return alert_batch


EMAIL_SUBJECT = "\U0001f6d2 PantryVision: You have products expiring in your pantry!"


def _format_short_date(iso_date: str) -> str:
    """Formats an ISO date string ("YYYY-MM-DD") as "{Mon} {day}" (e.g. "Jul 11").

    Built manually (strftime("%b") + date.day) instead of a platform-specific
    strftime flag like "%-d", since Windows does not support that flag and
    this function must behave identically across operating systems.
    """
    date_obj = datetime.strptime(iso_date, "%Y-%m-%d").date()
    return f"{date_obj.strftime('%b')} {date_obj.day}"


def build_email_body(alert_batch: AlertBatch, current_date: date) -> tuple[str, str]:
    """
    Pure function: builds (subject, HTML body) grouping expired and
    expiring-soon products into separate styled tables.

    current_date is passed in (rather than calling date.today() internally)
    so the function stays pure/deterministic and testable: it is needed to
    compute the "Yesterday" / "Today" / "In N days" relative labels from the
    ISO expiration_date strings stored on each ClassifiedProduct.

    Per the design, this is only ever invoked with a non-empty alert_batch
    (lambda_handler only calls it when the batch is non-empty), but it is
    written to handle an empty batch gracefully rather than crash, in case
    that assumption is ever violated.

    product_name comes from stored DynamoDB data and could theoretically
    contain HTML special characters, so it is escaped with html.escape()
    before interpolation to prevent broken markup or HTML injection.
    """
    subject = EMAIL_SUBJECT

    if not alert_batch:
        return subject, (
            "<html><body><p>Good news! No products are expiring or expired "
            "right now.</p></body></html>"
        )

    expired = [p for p in alert_batch if p["classification"] == "Expired_Product"]
    expiring = [p for p in alert_batch if p["classification"] == "Expiring_Product"]

    row_template = (
        '<tr style="background-color: {bg};">'
        '<td style="padding: 10px 12px; color: {fg}; font-weight: bold;">{name}</td>'
        '<td style="padding: 10px 12px; color: {fg};">{expiration}</td>'
        '<td style="padding: 10px 12px; color: {fg};">{status}</td>'
        "</tr>"
    )

    expired_block = ""
    if expired:
        rows = []
        for product in expired:
            name = html.escape(product["product_name"])
            expiration_date_obj = datetime.strptime(
                product["expiration_date"], "%Y-%m-%d"
            ).date()
            days_until_expiration = (expiration_date_obj - current_date).days
            expiration_label = _format_short_date(product["expiration_date"])
            if days_until_expiration == -1:
                expiration_label += " (Yesterday)"

            rows.append(
                row_template.format(
                    bg="#FEE2E2",
                    fg="#991B1B",
                    name=name,
                    expiration=expiration_label,
                    status="\U0001f5d1\ufe0f Expired",
                )
            )

        expired_block = (
            '      <h3 style="color: #991B1B;">\u274c Expired products (toss or remove)</h3>\n'
            '      <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">\n'
            "        <tbody>\n"
            f"          {''.join(rows)}\n"
            "        </tbody>\n"
            "      </table>\n"
        )

    expiring_block = ""
    if expiring:
        rows = []
        for product in expiring:
            name = html.escape(product["product_name"])
            expiration_date_obj = datetime.strptime(
                product["expiration_date"], "%Y-%m-%d"
            ).date()
            days_until_expiration = (expiration_date_obj - current_date).days
            expiration_label = _format_short_date(product["expiration_date"])

            if days_until_expiration == 0:
                status = "\u23f3 Today"
            elif days_until_expiration == 1:
                status = "\u23f3 In 1 day"
            else:
                status = f"\u23f3 In {days_until_expiration} days"

            rows.append(
                row_template.format(
                    bg="#F3E8FF",
                    fg="#6B21A8",
                    name=name,
                    expiration=expiration_label,
                    status=status,
                )
            )

        expiring_block = (
            '      <h3 style="color: #6B21A8;">\u23f0 Expiring this week (use them soon!)</h3>\n'
            '      <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">\n'
            "        <tbody>\n"
            f"          {''.join(rows)}\n"
            "        </tbody>\n"
            "      </table>\n"
        )

    body = (
        "<html>\n"
        '  <body style="font-family: Arial, sans-serif; color: #333333; margin: 0; padding: 0;">\n'
        '    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">\n'
        '      <h2>Hi there! \U0001f9fa</h2>\n'
        "      <p>We checked your pantry and found a few products you should "
        "look at today to make the most of your groceries:</p>\n"
        f"{expired_block}"
        f"{expiring_block}"
        '      <p style="color: #999999; font-size: 12px;">Put together with '
        "care by PantryVision, to help you take care of your home and save "
        "money. \U0001f49c</p>\n"
        "    </div>\n"
        "  </body>\n"
        "</html>"
    )

    return subject, body


# SES send retries: up to 2 additional attempts (3 total), per Requirement
# 3.3. A daily alert email is not urgent enough to warrant a longer/faster
# backoff, and a minimum 2s delay keeps the total retry window small enough
# to stay well within the Lambda's execution budget.
MAX_SES_SEND_ATTEMPTS = 3
SES_RETRY_DELAY_SECONDS = 2

# Error codes that represent a temporary SES/service condition likely to
# succeed on retry (Requirement 3.3) - throttling and upstream service
# hiccups are transient by nature, not caused by anything in the request
# itself.
TRANSIENT_SES_ERROR_CODES = {
    "Throttling",
    "ThrottlingException",
    "ServiceUnavailable",
    "InternalFailure",
}

# Error codes that indicate the request itself is invalid/rejected and will
# fail identically on every retry (Requirement 3.4) - retrying would just
# waste the Lambda's time budget and delay the failure log with no chance
# of success.
NON_TRANSIENT_SES_ERROR_CODES = {
    "MessageRejected",
    "MailFromDomainNotVerified",
    "AccountSendingPausedException",
    "ConfigurationSetDoesNotExist",
}


def send_alert_email(
    ses_client, sender: str, recipient: str, subject: str, body: str
) -> DeliveryResult:
    """Sends the Alert_Email via SES.

    Retries up to 2 additional times (3 attempts total) when SES reports a
    transient error (throttling/service-side issues), waiting at least
    SES_RETRY_DELAY_SECONDS between attempts (Requirement 3.3). Does not
    retry non-transient errors (e.g. an unverified identity or a malformed
    request) since those will fail identically on every attempt
    (Requirement 3.4). Returns a DeliveryResult describing the outcome;
    failure_reason is always an SES-provided error code/message, never the
    sender/recipient address or product data (Requirement 3.5).
    """
    last_failure_reason: str | None = None

    for attempt in range(1, MAX_SES_SEND_ATTEMPTS + 1):
        try:
            ses_client.send_email(
                Source=sender,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Html": {"Data": body}},
                },
            )
            return DeliveryResult(status="sent", failure_reason=None)
        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code", "Unknown")
            error_message = error.response.get("Error", {}).get("Message", "")
            last_failure_reason = f"{error_code}: {error_message}" if error_message else error_code

            # Only codes explicitly known to be transient are retried; any
            # other code (including unrecognized ones) is treated as
            # non-transient to avoid retrying a request that is guaranteed
            # to fail again, per Requirement 3.4.
            is_transient = error_code in TRANSIENT_SES_ERROR_CODES
            if not is_transient:
                return DeliveryResult(status="failed", failure_reason=last_failure_reason)

            if attempt < MAX_SES_SEND_ATTEMPTS:
                time.sleep(SES_RETRY_DELAY_SECONDS)

    return DeliveryResult(status="failed", failure_reason=last_failure_reason)


def log_run_summary(
    expiring_count: int,
    expired_count: int,
    status: str,
    failure_reason: str | None = None,
) -> None:
    """
    Logs a single structured summary line to CloudWatch. Never includes
    email addresses, image keys, or product-level PII beyond product name
    counts.

    Per Requirement 5.4 and design Property 12, only pre-aggregated,
    non-sensitive values are ever passed to the logger here: integer counts,
    the delivery status string ("sent" | "not-needed" | "failed"), and the
    SES-provided failure reason (an AWS error code/message, not user data).
    Raw product dicts, `imageKey` values, and the configured sender/recipient
    addresses must never reach this function.
    """
    summary = {
        "expiring_count": expiring_count,
        "expired_count": expired_count,
        "status": status,
    }

    # Only include the failure reason when the run actually failed, per
    # Requirement 5.2 ("log the specific failure reason ... WHEN the
    # delivery status is 'failed'").
    if status == "failed" and failure_reason is not None:
        summary["failure_reason"] = failure_reason

    logger.info("run_summary=%s", summary)


def lambda_handler(event, context) -> dict:
    """Entry point invoked by the Daily_Schedule EventBridge rule.

    Orchestrates the full run: validate config -> scan -> classify ->
    (conditionally) build + send email -> log summary. This is the only
    place in the module with cross-function control flow branching; every
    other function stays a single-responsibility, independently testable
    unit (see design.md's Components and Interfaces section).
    """
    # Step 1: configuration must be valid before any AWS call is made
    # (Requirement 2.8). A ConfigurationError is an expected/handled
    # condition, not a crash, so it is caught here rather than falling
    # through to the top-level except below. log_run_summary is
    # deliberately NOT called here: there are no expiring/expired counts
    # yet (no scan happened), so a summary line would be misleading.
    #
    # Steps 1-6 all live inside a single top-level try/except so any
    # unhandled error (Requirement 5.3), including one raised from
    # get_alert_config itself, is caught by the generic `except Exception`
    # below. ConfigurationError and ScanFailedError are handled by their
    # own specific except clauses (which run first, since they are more
    # specific than the catch-all), so their expected/handled outcomes
    # never fall through to the generic unhandled-error path.
    try:
        config = get_alert_config()
        table = _dynamodb_resource.Table(config["table_name"])

        # Step 3: scan the table. A ScanFailedError means no reliable
        # product data is available, so - like the config error above -
        # log_run_summary is skipped (no valid counts exist) in favor of a
        # dedicated error log, and no email is ever attempted
        # (Requirement 2.6). Handled by the ScanFailedError except clause
        # below, which runs before the generic catch-all.
        products = scan_products(table)

        # Step 4: classify. This is a pure, deterministic function, so any
        # failure past this point always has valid counts to log. today is
        # computed once and reused for build_email_body below, so
        # classification and display always agree on "today".
        today = date.today()
        alert_batch = classify_products(products, today)
        expiring_count = sum(
            1 for p in alert_batch if p["classification"] == "Expiring_Product"
        )
        expired_count = sum(
            1 for p in alert_batch if p["classification"] == "Expired_Product"
        )

        # Step 5: an empty batch never triggers an email (Requirement 2.4),
        # but the run still completed successfully, so it is always
        # reflected in the summary log (Requirement 5.1).
        if not alert_batch:
            log_run_summary(
                expiring_count=0, expired_count=0, status="not-needed"
            )
            return {
                "statusCode": 200,
                "expiring_count": 0,
                "expired_count": 0,
                "status": "not-needed",
            }

        # Step 6: non-empty batch -> build and send exactly one email, then
        # log the actual outcome (Requirements 2.2, 2.3, 5.1, 5.2).
        subject, body = build_email_body(alert_batch, today)
        result = send_alert_email(
            _ses_client,
            config["sender_address"],
            config["recipient_address"],
            subject,
            body,
        )
        log_run_summary(
            expiring_count,
            expired_count,
            status=result["status"],
            failure_reason=result.get("failure_reason"),
        )

        return {
            "statusCode": 200,
            "expiring_count": expiring_count,
            "expired_count": expired_count,
            "status": result["status"],
        }
    except ConfigurationError as error:
        # The exception message names which variable is missing, never its
        # value, so this is safe to log directly (Requirement 5.4).
        logger.error("configuration_error=%s", str(error))
        return {"statusCode": 200, "body": "skipped: configuration error"}
    except ScanFailedError:
        logger.error("Product scan failed after retries")
        return {"statusCode": 200, "body": "skipped: scan failed"}
    except Exception:
        # Catch-all for anything unexpected (Requirement 5.3). logger.exception
        # logs the exception message/traceback; by design, no stage above
        # ever passes raw product data, image keys, or email addresses into
        # an exception message, so this stays consistent with the
        # no-PII-in-logs policy (Requirement 5.4) for the MVP.
        logger.exception("unhandled_error=lambda_handler")
        return {"statusCode": 500, "body": "failed: unhandled error"}
