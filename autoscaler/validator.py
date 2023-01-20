"""This is an addon module to for cerberus validator

This class component is used to validate when autoscaledown is True,
operate_day component should be there.
"""

from cerberus import Validator, errors


class AutoscalerValidator(Validator):
  def _check_with_operation(self, field, value):
    if field == "autoscaledown" and value:
      if "operate_day" not in self.document:
        self._error("operate_day", errors.REQUIRED_FIELD, "check_with")
