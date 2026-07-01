function createBlockState(data = null) {
  return {
    data,
    loading: false,
    error: null,
    loaded: false,
  };
}

function normalizeBlockError(error) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return String(error || '请求失败');
}

function startBlock(block, keepData = true) {
  return {
    data: keepData ? block?.data ?? null : null,
    loading: true,
    error: null,
    loaded: Boolean(keepData && block?.loaded),
  };
}

function resolveBlock(data) {
  return {
    data: data ?? null,
    loading: false,
    error: null,
    loaded: true,
  };
}

function rejectBlock(block, error, keepData = true) {
  return {
    data: keepData ? block?.data ?? null : null,
    loading: false,
    error: normalizeBlockError(error),
    loaded: Boolean(keepData && block?.loaded),
  };
}

export {
  createBlockState,
  normalizeBlockError,
  startBlock,
  resolveBlock,
  rejectBlock,
};
