# Curvature computation mode — controls the importance pipeline's curvature stage.
# Valid values:
#   "fast"      — normal variation (no scipy, ~66ms/component, good for dev/demos)
#   "balanced"  — angle-deficit / vectorized Gaussian (not yet implemented)
#   "accurate"  — discrete mean curvature via scipy (~3.7s/component, reference)
# Default: "fast"
CURVATURE_MODE: str = "fast"
