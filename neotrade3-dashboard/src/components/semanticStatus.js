const TONE_CLASS_MAP = {
  entry: 'bg-green-50 text-green-700 border-green-100',
  exit: 'bg-red-50 text-red-700 border-red-100',
  watch: 'bg-blue-50 text-blue-700 border-blue-100',
  inactive: 'bg-gray-50 text-gray-700 border-gray-100',
  inactiveStrong: 'bg-gray-100 text-gray-700 border-gray-200',
  riskWarn: 'bg-orange-50 text-orange-700 border-orange-100',
  pending: 'bg-blue-50 text-blue-700 border-blue-100',
  done: 'bg-gray-100 text-gray-700 border-gray-200',
};

const SEMANTIC_STATUS_MAP = {
  entry_ready: {
    label: '可出手',
    group: '建仓',
    description: '当前对象满足建仓或出手条件，可进入建仓流程。',
    trigger: '适用于买入信号成立、且当前允许出手的对象。',
    difference: '与“跟踪观察”不同，该状态代表当前可以执行而不是仅观察。',
    tone: 'entry',
  },
  entry_queued: {
    label: '已排队',
    group: '建仓',
    description: '建仓动作已生成，等待后续执行日处理。',
    trigger: '适用于已生成买入意图、但尚未执行的对象。',
    difference: '与“可出手”不同，该状态表示动作已经进入执行队列。',
    tone: 'watch',
  },
  exit_signal: {
    label: '离场信号',
    group: '离场',
    description: '已有持仓出现明确退出动作信号，应进入离场处理。',
    trigger: '适用于已有仓位命中止损、板块冷却等退出条件的对象。',
    difference: '与“回避”不同，该状态面向已有仓位，而不是禁入新仓。',
    tone: 'exit',
  },
  exit_risk_stop: {
    label: '风险退出',
    group: '离场',
    description: '已有持仓因风险控制触发退出，而不是一般观察结论。',
    trigger: '适用于止损、追踪止损或其他风险控制主导的退出场景。',
    difference: '它属于“离场”的原因分类，不是独立于离场之外的状态。',
    tone: 'exit',
  },
  exit_sector_cooldown: {
    label: '板块冷却退出',
    group: '离场',
    description: '板块人气冷却或主线衰减，已有持仓进入退出处理。',
    trigger: '适用于板块冷却、跟随股溃散等板块级退出条件成立时。',
    difference: '与“回避”不同，它针对的是已有仓位的退出，而不是新仓禁入。',
    tone: 'exit',
  },
  watch_general: {
    label: '观察',
    group: '跟踪观察',
    description: '当前对象进入持续观察名单，但还不构成立即建仓动作。',
    trigger: '适用于策略仍需继续观察、但当前未触发执行条件的对象。',
    difference: '与“不满足条件”不同，该状态强调继续跟踪而非直接排除。',
    tone: 'watch',
  },
  watch_follower: {
    label: '跟随观察',
    group: '跟踪观察',
    description: '当前对象属于跟随角色，纳入观察但不是当前优先建仓对象。',
    trigger: '适用于角色为跟随、需要继续观察节奏和强度的对象。',
    difference: '它仍在观察池内，不等于条件失败。',
    tone: 'watch',
  },
  not_qualified_avoid: {
    label: '回避',
    group: '不满足条件',
    description: '当前对象不建议新开仓参与，应从建仓动作中排除。',
    trigger: '适用于风险过高、语境为禁入，或当前不适合参与的对象。',
    difference: '与“离场信号”不同，回避不表示已有仓位应卖出。',
    tone: 'inactive',
  },
  not_qualified_market: {
    label: '大盘不配合',
    group: '不满足条件',
    description: '当前大盘环境不支持该对象出手，未满足建仓前提。',
    trigger: '适用于市场环境过滤条件未通过的对象。',
    difference: '这是环境不满足，不等于对象本身强度为零。',
    tone: 'inactive',
  },
  not_qualified_concept: {
    label: '题材不配合',
    group: '不满足条件',
    description: '当前题材或板块强度不足，未满足建仓条件。',
    trigger: '适用于题材共振、主线配合等条件未通过的对象。',
    difference: '它强调题材层条件不足，不等于个股必然走弱。',
    tone: 'inactive',
  },
  not_qualified_momentum: {
    label: '动能不足',
    group: '不满足条件',
    description: '当前个股信号强度不足，尚未达到建仓门槛。',
    trigger: '适用于动能、趋势或强度门槛未通过的对象。',
    difference: '它强调个股层信号不足，不等于完全放弃后续观察。',
    tone: 'inactive',
  },
  abandoned: {
    label: '已放弃',
    group: '不满足条件',
    description: '该对象已被人工明确放弃，不再继续进入当前建仓流程。',
    trigger: '适用于人工主动放弃或取消当前对象的场景。',
    difference: '它强调人为决策，不等于系统自动判定的失败。',
    tone: 'inactiveStrong',
  },
  risk_ok: {
    label: '稳定状态',
    group: '风险标签',
    description: '当前未出现预警级或退出级风险，风险状态稳定。',
    trigger: '适用于 risk_level = ok 的对象。',
    difference: '它表达风险层状态，并不等于一定满足建仓条件。',
    tone: 'entry',
  },
  risk_warn: {
    label: '危险状态',
    group: '风险标签',
    description: '当前出现预警级风险，需要重点跟踪，但未必立即退出。',
    trigger: '适用于 risk_level = warn 的对象。',
    difference: '与“离场信号”不同，它是风险预警，不一定直接触发卖出。',
    tone: 'riskWarn',
  },
  queue_pending: {
    label: '待处理',
    group: '执行队列状态',
    description: '动作已生成，当前尚未执行，也未取消。',
    trigger: '适用于执行队列 status = pending 的动作。',
    difference: '与“已处理”不同，该状态仍可继续执行或取消。',
    tone: 'pending',
  },
  queue_executed: {
    label: '已处理',
    group: '执行队列状态',
    description: '该动作已经完成处理，不再处于待执行状态。',
    trigger: '适用于执行队列 status = executed 的动作。',
    difference: '该状态只描述流程结果，不再表达买卖方向本身。',
    tone: 'done',
  },
  queue_cancelled: {
    label: '已取消',
    group: '执行队列状态',
    description: '该动作已被取消，不再继续执行。',
    trigger: '适用于执行队列 status = cancelled 的动作。',
    difference: '与“已放弃”不同，它可以是系统或其它原因触发的取消。',
    tone: 'inactiveStrong',
  },
  queue_abandoned: {
    label: '已放弃',
    group: '执行队列状态',
    description: '该动作被人工主动放弃，不再继续执行。',
    trigger: '适用于执行队列中因 abandoned 原因取消的动作。',
    difference: '它强调人为放弃，而不是一般性的取消。',
    tone: 'inactiveStrong',
  },
  check_pass: {
    label: '通过',
    group: '检查结果',
    description: '当前检查项通过，说明该检查项条件成立。',
    trigger: '适用于单股核验或筛选器核验 result = true 的结果。',
    difference: '检查项通过不等于一定立即建仓，仍需结合其它信号判断。',
    tone: 'entry',
  },
  check_fail: {
    label: '未通过',
    group: '检查结果',
    description: '当前检查项未通过，说明该检查项条件不成立。',
    trigger: '适用于单股核验或筛选器核验 result = false 的结果。',
    difference: '检查项未通过不等于离场信号，它只说明该检查项未成立。',
    tone: 'exit',
  },
};

function getSemanticStatusDefinition(semanticKey) {
  return SEMANTIC_STATUS_MAP[String(semanticKey || '').trim()] || null;
}

function getSemanticStatusClasses(semanticKey) {
  const definition = getSemanticStatusDefinition(semanticKey);
  const tone = definition?.tone || 'inactive';
  return TONE_CLASS_MAP[tone] || TONE_CLASS_MAP.inactive;
}

function buildSemanticStatusTitle(semanticKey, labelOverride) {
  const definition = getSemanticStatusDefinition(semanticKey);
  if (!definition) return String(labelOverride || semanticKey || '').trim();

  const lines = [
    String(labelOverride || definition.label || '').trim(),
    `一级状态：${definition.group}`,
    `含义：${definition.description}`,
    `触发条件：${definition.trigger}`,
  ];
  if (definition.difference) {
    lines.push(`区别：${definition.difference}`);
  }
  return lines.join('\n');
}

export {
  buildSemanticStatusTitle,
  getSemanticStatusClasses,
  getSemanticStatusDefinition,
};
