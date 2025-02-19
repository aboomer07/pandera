"""Pandera array backends."""

import traceback
from typing import cast, Iterable, NamedTuple, Optional

import pandas as pd
from multimethod import DispatchError

from pandera.backends.pandas.base import PandasSchemaBackend
from pandera.backends.pandas.error_formatters import (
    reshape_failure_cases,
    scalar_failure_case,
)
from pandera.backends.pandas.utils import convert_uniquesettings
from pandera.api.pandas.types import is_field
from pandera.engines.pandas_engine import Engine
from pandera.error_handlers import SchemaErrorHandler
from pandera.errors import ParserError, SchemaError, SchemaErrors


class CoreCheckResult(NamedTuple):
    """Namedtuple for holding results of core checks."""

    check: str
    reason_code: str
    passed: bool
    message: Optional[str] = None
    failure_cases: Optional[Iterable] = None


class ArraySchemaBackend(PandasSchemaBackend):
    """Backend for pandas arrays."""

    def preprocess(self, check_obj, inplace: bool = False):
        return check_obj if inplace else check_obj.copy()

    def validate(
        self,
        check_obj,
        schema,
        *,
        head: Optional[int] = None,
        tail: Optional[int] = None,
        sample: Optional[int] = None,
        random_state: Optional[int] = None,
        lazy: bool = False,
        inplace: bool = False,
    ):
        # pylint: disable=too-many-locals
        error_handler = SchemaErrorHandler(lazy)
        check_obj = self.preprocess(check_obj, inplace)

        if schema.coerce:
            try:
                check_obj = self.coerce_dtype(
                    check_obj, schema=schema, error_handler=error_handler
                )
            except SchemaError as exc:
                error_handler.collect_error(exc.reason_code, exc)

        field_obj_subsample = self.subsample(
            check_obj if is_field(check_obj) else check_obj[schema.name],
            head,
            tail,
            sample,
            random_state,
        )

        check_obj_subsample = self.subsample(
            check_obj,
            head,
            tail,
            sample,
            random_state,
        )

        # run the core checks
        for core_check in (
            self.check_name,
            self.check_nullable,
            self.check_unique,
            self.check_dtype,
        ):
            check_result = core_check(field_obj_subsample, schema)
            if not check_result.passed:
                error_handler.collect_error(
                    check_result.reason_code,
                    SchemaError(
                        schema=schema,
                        data=check_obj,
                        message=check_result.message,
                        failure_cases=check_result.failure_cases,
                        check=check_result.check,
                        reason_code=check_result.reason_code,
                    ),
                )

        check_results = self.run_checks(
            check_obj_subsample, schema, error_handler, lazy
        )
        assert all(check_results)

        if lazy and error_handler.collected_errors:
            raise SchemaErrors(
                schema=schema,
                schema_errors=error_handler.collected_errors,
                data=check_obj,
            )
        return check_obj

    def coerce_dtype(
        self,
        check_obj,
        *,
        schema=None,
        # pylint: disable=unused-argument
        error_handler: SchemaErrorHandler = None,
    ):
        """Coerce type of a pd.Series by type specified in dtype.

        :param pd.Series series: One-dimensional ndarray with axis labels
            (including time series).
        :returns: ``Series`` with coerced data type
        """
        assert schema is not None, "The `schema` argument must be provided."
        if schema.dtype is None or not schema.coerce:
            return check_obj

        try:
            return schema.dtype.try_coerce(check_obj)
        except ParserError as exc:
            raise SchemaError(
                schema=schema,
                data=check_obj,
                message=(
                    f"Error while coercing '{schema.name}' to type "
                    f"{schema.dtype}: {exc}:\n{exc.failure_cases}"
                ),
                failure_cases=exc.failure_cases,
                check=f"coerce_dtype('{schema.dtype}')",
            ) from exc

    def check_name(self, check_obj: pd.Series, schema):
        return CoreCheckResult(
            check=f"field_name('{schema.name}')",
            reason_code="wrong_field_name",
            passed=schema.name is None or check_obj.name == schema.name,
            message=(
                f"Expected {type(check_obj)} to have name '{schema.name}', "
                f"found '{check_obj.name}'"
            ),
            failure_cases=scalar_failure_case(check_obj.name),
        )

    def check_nullable(self, check_obj: pd.Series, schema):
        isna = check_obj.isna()
        passed = schema.nullable or not isna.any()
        return CoreCheckResult(
            check="not_nullable",
            reason_code="series_contains_nulls",
            passed=cast(bool, passed),
            message=(
                f"non-nullable series '{check_obj.name}' contains "
                f"null values:\n{check_obj[isna]}"
            ),
            failure_cases=reshape_failure_cases(
                check_obj[isna], ignore_na=False
            ),
        )

    def check_unique(self, check_obj: pd.Series, schema):
        passed = True
        failure_cases = None
        message = None

        if schema.unique:
            keep_argument = convert_uniquesettings(schema.report_duplicates)
            if type(check_obj).__module__.startswith("pyspark.pandas"):
                # pylint: disable=import-outside-toplevel
                import pyspark.pandas as ps

                duplicates = (
                    check_obj.to_frame()  # type: ignore
                    .duplicated(keep=keep_argument)  # type: ignore
                    .reindex(check_obj.index)
                )
                with ps.option_context("compute.ops_on_diff_frames", True):
                    failed = check_obj[duplicates]
            else:
                duplicates = check_obj.duplicated(keep=keep_argument)  # type: ignore
                failed = check_obj[duplicates]

            if duplicates.any():
                passed = False
                failure_cases = reshape_failure_cases(failed)
                message = (
                    f"series '{check_obj.name}' contains duplicate "
                    f"values:\n{failed}"
                )

        return CoreCheckResult(
            check="field_uniqueness",
            reason_code="series_contains_duplicates",
            passed=passed,
            message=message,
            failure_cases=failure_cases,
        )

    def check_dtype(self, check_obj: pd.Series, schema):
        passed = True
        failure_cases = None
        msg = None

        if schema.dtype is not None:
            dtype_check_results = schema.dtype.check(
                Engine.dtype(check_obj.dtype),
                check_obj,
            )
            if isinstance(dtype_check_results, bool):
                passed = dtype_check_results
                failure_cases = scalar_failure_case(str(check_obj.dtype))
                msg = (
                    f"expected series '{check_obj.name}' to have type "
                    f"{schema.dtype}, got {check_obj.dtype}"
                )
            else:
                passed = dtype_check_results.all()
                failure_cases = reshape_failure_cases(
                    check_obj[~dtype_check_results.astype(bool)],
                    ignore_na=False,
                )
                msg = (
                    f"expected series '{check_obj.name}' to have type "
                    f"{schema.dtype}:\nfailure cases:\n{failure_cases}"
                )

        return CoreCheckResult(
            check=f"dtype('{schema.dtype}')",
            reason_code="wrong_dtype",
            passed=passed,
            message=msg,
            failure_cases=failure_cases,
        )

    # pylint: disable=unused-argument
    def run_checks(self, check_obj, schema, error_handler, lazy):
        check_results = []
        for check_index, check in enumerate(schema.checks):
            check_args = [None] if is_field(check_obj) else [schema.name]
            try:
                check_results.append(
                    self.run_check(
                        check_obj,
                        schema,
                        check,
                        check_index,
                        *check_args,
                    )
                )
            except SchemaError as err:
                error_handler.collect_error("dataframe_check", err)
            except Exception as err:  # pylint: disable=broad-except
                # catch other exceptions that may occur when executing the Check
                if isinstance(err, DispatchError):
                    # if the error was raised by a check registered via
                    # multimethod, get the underlying __cause__
                    err = err.__cause__
                err_msg = f'"{err.args[0]}"' if len(err.args) > 0 else ""
                err_str = f"{err.__class__.__name__}({ err_msg})"
                error_handler.collect_error(
                    "check_error",
                    SchemaError(
                        schema=schema,
                        data=check_obj,
                        message=(
                            f"Error while executing check function: {err_str}\n"
                            + traceback.format_exc()
                        ),
                        failure_cases=scalar_failure_case(err_str),
                        check=check,
                        check_index=check_index,
                    ),
                    original_exc=err,
                )
        return check_results


class SeriesSchemaBackend(ArraySchemaBackend):
    """Backend for pandas Series objects."""

    def coerce_dtype(
        self,
        check_obj,
        *,
        schema=None,
        error_handler: SchemaErrorHandler = None,
    ):
        if hasattr(check_obj, "pandera"):
            check_obj = check_obj.pandera.add_schema(schema)

        check_obj = super().coerce_dtype(
            check_obj, schema=schema, error_handler=error_handler
        )

        if hasattr(check_obj, "pandera"):
            check_obj = check_obj.pandera.add_schema(schema)
        return check_obj
