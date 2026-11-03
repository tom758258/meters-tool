export function inferTransportScope(resource) {
  const normalized = String(resource || "").trim().toUpperCase();
  if (normalized.startsWith("USB")) {
    return "usb";
  }
  if (normalized.startsWith("TCPIP")) {
    return "tcpip";
  }
  return null;
}

export function findProductSupportScope(resource, liveSupport, visaLibrary = "") {
  if (visaLibrary !== "" && visaLibrary !== "@py") return null;
  const normalizedResource = String(resource || "").trim();
  const transport = inferTransportScope(normalizedResource) || (
    normalizedResource ? null : liveSupport?.transport_scope
  );
  if (!transport) {
    return null;
  }
  return (liveSupport?.scopes || []).find(
    (scope) => scope.transport_scope === transport && scope.backend_scope === (visaLibrary === "@py" ? "pyvisa_py" : "system_visa")
  ) || null;
}

// Discovery presentation only. Product authorization remains in Core.
export function scannedResourceConnectionStatus(item, supportedDevices, visaLibrary = "") {
  if (item?.live !== true) return "unavailable";
  if (!item.instrument_model || !item.instrument_model_id) return "unsupported_model";
  if (!Array.isArray(supportedDevices)) return "unavailable";
  const backend = visaLibrary === "@py" ? "pyvisa_py"
    : visaLibrary === "" ? "system_visa" : null;
  if (!backend) return "unavailable";
  const transport = inferTransportScope(item.resource);
  if (!transport) return "unsupported_connection";
  const model = supportedDevices.find((device) => device.model === item.instrument_model);
  const transports = model?.backend_connections?.[backend];
  return Array.isArray(transports) && transports.includes(transport)
    ? "supported" : "unsupported_connection";
}

export function featureAvailability(scope, featureKind, featureValue) {
  if (!scope) {
    return {
      available: false,
      reasonKey: "support.reason.scope_unavailable",
      validationStatus: "missing",
    };
  }
  if (scope.validation_status !== "live_validated_full_suite") {
    const notSupported = scope.validation_status === "not_supported_by_model";
    return {
      available: false,
      reasonKey: notSupported
        ? "support.reason.not_supported_by_model"
        : "support.reason.pending_live_validation",
      validationStatus: scope.validation_status || "missing",
    };
  }
  const feature = scope.features?.[featureKind]?.[featureValue];
  const validationStatus = feature?.validation_status || "missing";
  if (validationStatus === "live_validated_full_suite") {
    return { available: true, reasonKey: null, validationStatus };
  }
  if (validationStatus === "feature_pending") {
    return {
      available: false,
      reasonKey: "support.reason.pending_live_validation",
      validationStatus,
    };
  }
  if (validationStatus === "not_supported_by_model") {
    return {
      available: false,
      reasonKey: "support.reason.not_supported_by_model",
      validationStatus,
    };
  }
  return {
    available: false,
    reasonKey: "support.reason.scope_unavailable",
    validationStatus,
  };
}

export function supportsAutoZero(measurement) {
  const options = measurement?.auto_zero_options;
  return (
    measurement?.supports_auto_zero === true &&
    Array.isArray(options) &&
    options.length > 1
  );
}

export function supportsAcBandwidth(measurement) {
  return Boolean(measurement?.supports_ac_bandwidth);
}

export function supportsCurrentTerminal(measurement) {
  return Boolean(measurement?.supports_current_terminal);
}

export function supportsGateTime(measurement) {
  return Boolean(measurement?.supports_gate_time);
}

export function supportsFreqPeriodTimeout(measurement) {
  return Boolean(measurement?.supports_freq_period_timeout);
}

export function supportsDcvInputZ(measurement) {
  const options = measurement?.dcv_input_impedance_options;
  return (
    measurement?.supports_dcv_input_impedance === true &&
    Array.isArray(options) &&
    options.length > 0
  );
}

export function usesTriggerTimeout(mode, triggerModeMetadata) {
  return triggerModeMetadata?.[mode]?.uses_trigger_timeout === true;
}

export function isCustomMode(mode) {
  return String(mode || "").endsWith("-custom");
}

export function isHardwareMode(mode) {
  return mode === "external" || mode === "external-custom";
}

export function isSoftwareTriggeredMode(mode) {
  return mode === "software" || mode === "software-custom";
}

export function modeScopeVisible(scope, mode, triggerModeMetadata) {
  if (scope === "simple") {
    return !isCustomMode(mode);
  }
  if (scope === "custom") {
    return isCustomMode(mode);
  }
  if (scope === "hardware") {
    return isHardwareMode(mode);
  }
  if (scope === "software") {
    return mode === "software";
  }
  if (scope === "software-trigger") {
    return isSoftwareTriggeredMode(mode);
  }
  if (scope === "trigger-timeout") {
    return usesTriggerTimeout(mode, triggerModeMetadata);
  }
  return true;
}
