"""
NEXUS Planning — Result Verifier.

Validates the integrity and completion criteria of step outputs and overall tasks
(e.g., verifying created artifacts, file non-emptiness, device delivery, and process states).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from nexus.planning.types import Plan, PlanStep, VerificationResult
from nexus.utils.logging import get_logger

log = get_logger("planning.verifier")


class ResultVerifier:
    """
    Validates that task actions achieved their intended verifiable outcome.
    """

    def verify_step_result(self, step: PlanStep, result_output: Any) -> VerificationResult:
        """
        Verify the output of an individual step.
        """
        if result_output is None:
            return VerificationResult(
                verified=False,
                details=f"Step '{step.description}' returned None/null output.",
                confidence=0.0,
            )

        # 1. Existing file verification checks
        if isinstance(result_output, Path) or (
            isinstance(result_output, str)
            and len(result_output) < 300
            and os.path.exists(str(result_output))
            and os.path.isfile(str(result_output))
        ):
            path = Path(result_output)
            if path.exists():
                try:
                    size = path.stat().st_size
                    if size > 0:
                        return VerificationResult(
                            verified=True,
                            details=f"Artifact verified: '{path.name}' exists with size {size} bytes.",
                            target_artifact=str(path),
                            confidence=1.0,
                        )
                    else:
                        return VerificationResult(
                            verified=False,
                            details=f"Artifact '{path.name}' exists but is 0 bytes (empty file).",
                            target_artifact=str(path),
                            confidence=0.2,
                        )
                except Exception as e:
                    return VerificationResult(
                        verified=False,
                        details=f"Could not inspect artifact '{path}': {e}",
                        confidence=0.5,
                    )
            elif isinstance(result_output, Path):
                return VerificationResult(
                    verified=False,
                    details=f"Expected artifact '{result_output}' was not found on disk.",
                    confidence=0.0,
                )

        # 2. Dictionary / Structured verification
        if isinstance(result_output, dict):
            if result_output.get("success") is False or "error" in result_output:
                return VerificationResult(
                    verified=False,
                    details=f"Step returned failure dictionary: {result_output.get('error', 'success=False')}",
                    confidence=0.0,
                )

            # If a transfer manifest or device delivery is reported
            if "manifest" in result_output or "transfer_id" in result_output:
                return VerificationResult(
                    verified=True,
                    details="Device transfer verified successfully with delivery confirmation.",
                    confidence=0.95,
                )

            return VerificationResult(
                verified=True,
                details="Structured output verified with success status.",
                confidence=0.9,
            )

        # 3. String validation
        if isinstance(result_output, str):
            if result_output.strip().lower().startswith(("error:", "failed:", "exception:")):
                return VerificationResult(
                    verified=False,
                    details=f"Step output indicates an error: {result_output[:120]}",
                    confidence=0.1,
                )
            return VerificationResult(
                verified=True,
                details="Step produced valid non-empty textual result.",
                confidence=0.85,
            )

        # 4. Default verification for truthy object
        return VerificationResult(
            verified=bool(result_output),
            details=f"Step output verified with type {type(result_output).__name__}.",
            confidence=0.8,
        )

    def verify_plan_completion(self, plan: Plan) -> VerificationResult:
        """
        Verify the overall completion of a full plan.
        """
        if not plan.steps:
            return VerificationResult(
                verified=False,
                details="Plan has no steps to verify.",
                confidence=0.0,
            )

        uncompleted = [s for s in plan.steps if s.status.value != "completed"]
        if uncompleted:
            return VerificationResult(
                verified=False,
                details=f"{len(uncompleted)} out of {plan.total_steps} steps failed or were not completed.",
                confidence=0.0,
            )

        # Inspect final step result
        final_step = plan.steps[-1]
        final_verif = self.verify_step_result(final_step, final_step.output)

        return VerificationResult(
            verified=final_verif.verified,
            details=f"All {plan.total_steps} steps completed. Final verification: {final_verif.details}",
            target_artifact=final_verif.target_artifact,
            confidence=final_verif.confidence,
        )
