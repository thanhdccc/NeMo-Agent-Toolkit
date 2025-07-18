import logging
import json
import os
from aiq.builder.builder import Builder
from aiq.builder.function_info import FunctionInfo
from aiq.cli.register_workflow import register_function
from aiq.data_models.function import FunctionBaseConfig
from pydantic import Field

logger = logging.getLogger(__name__)


class YesterdayToolConfig(FunctionBaseConfig, name="compute_yesterday"):
    pass


@register_function(config_type=YesterdayToolConfig)
async def compute_yesterday(config: YesterdayToolConfig, builder: Builder):
    from datetime import datetime, timedelta

    async def _yesterday(current_date: str) -> str:
        try:
            iso_text = current_date.replace(" ", "T")
            dt = datetime.fromisoformat(iso_text)
            prev = dt - timedelta(days=1)
            return prev.date().isoformat()
        except Exception:
            logger.exception("Error parsing input in compute_yesterday")
            return "Error getting yesterday"

    yield FunctionInfo.from_fn(
        _yesterday,
        description=(
            "Given an ISO-like datetime string (e.g. '2025-06-15 10:30:00'), "
            "return the previous calendar day's date in 'YYYY-MM-DD' format."
        )
    )


class CurrentDateToolConfig(FunctionBaseConfig, name="compute_current_date"):
    pass


@register_function(config_type=CurrentDateToolConfig)
async def compute_current_date(config: CurrentDateToolConfig, builder: Builder):

    from datetime import datetime

    async def _current_date(unused: str) -> str:
        try:
            now = datetime.now()
            return now.isoformat()
        except Exception:
            logger.exception("Error Getting Current Date")
            return "Error Getting Current Date"

    yield FunctionInfo.from_fn(
        _current_date,
        description=(
            "Return the current calendar day's date in 'YYYY-MM-DD' format."
        )
    )


class RetrieveReportByDateConfig(FunctionBaseConfig, name="retrieve_report_by_date"):
    date_field: str = Field(
        "date", description="Document field holding the timestamp")


@register_function(config_type=RetrieveReportByDateConfig)
async def retrieve_report_by_date(config: RetrieveReportByDateConfig, builder: Builder):

    from dateutil.parser import parse as parse_date
    from datetime import timedelta
    from pymongo import MongoClient

    async def _query(start_date: str) -> str:
        try:
            host = os.getenv("MONGO_HOST", "localhost")
            port = os.getenv("MONGO_PORT", "27017")
            db_name = os.getenv("MONGO_DATABASE", "agents")
            user = os.getenv("MONGO_USERNAME", "root")
            password = os.getenv("MONGO_PASSWORD", "root")
            collection = os.getenv("MONGO_COLLECTION", "sales_report")

            uri = f"mongodb://{user}:{password}@{host}:{port}"
            client = MongoClient(uri)
            coll = client[db_name][collection]

            start_dt = parse_date(start_date).date()
            end_dt = parse_date(start_date).date()

            start_iso = start_dt.isoformat() + "T00:00:00"
            end_iso = (end_dt + timedelta(days=1)).isoformat() + "T00:00:00"

            query = {
                config.date_field: {
                    "$gte": start_iso,
                    "$lt":  end_iso
                }
            }

            docs = list(coll.find(query))

            return json.dumps(docs, default=str)
        except Exception:
            logger.exception("Error querying report by date range")
            return "Error querying report by date range"

    yield FunctionInfo.from_fn(
        _query,
        description=(
            "Given date string in ISO-like format, "
            "query MongoDB for documents in the specified collection "
            "whose date_field is within that date (inclusive), "
            "and return them as JSON."
        )
    )


class RetrieveReportByDateRangeConfig(FunctionBaseConfig, name="retrieve_report_by_date_range"):
    date_field: str = Field(
        "date", description="Document field holding the timestamp")


@register_function(config_type=RetrieveReportByDateRangeConfig)
async def retrieve_report_by_date_range(config: RetrieveReportByDateRangeConfig, builder: Builder):

    from dateutil.parser import parse as parse_date
    from datetime import timedelta
    from pymongo import MongoClient

    async def _query(start_date: str, end_date: str) -> str:
        try:
            host = os.getenv("MONGO_HOST", "localhost")
            port = os.getenv("MONGO_PORT", "27017")
            db_name = os.getenv("MONGO_DATABASE", "agents")
            user = os.getenv("MONGO_USERNAME", "root")
            password = os.getenv("MONGO_PASSWORD", "root")
            collection = os.getenv("MONGO_COLLECTION", "sales_report")

            uri = f"mongodb://{user}:{password}@{host}:{port}"
            client = MongoClient(uri)
            coll = client[db_name][collection]

            start_dt = parse_date(start_date).date()
            end_dt = parse_date(end_date).date(
            ) if end_date else parse_date(start_date).date()

            start_iso = start_dt.isoformat() + "T00:00:00"
            end_iso = (end_dt + timedelta(days=1)).isoformat() + "T00:00:00"

            query = {
                config.date_field: {
                    "$gte": start_iso,
                    "$lt":  end_iso
                }
            }

            docs = list(coll.find(query))

            return json.dumps(docs, default=str)
        except Exception:
            logger.exception("Error querying report by date range")
            return "Error querying report by date range"

    yield FunctionInfo.from_fn(
        _query,
        description=(
            "Given a start and end date string in ISO-like format, "
            "query MongoDB for all documents in the specified collection "
            "whose date_field is within that date range (inclusive), "
            "and return them as JSON."
        )
    )
