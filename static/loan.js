/* 贷款违约模块 */
(async function () {
  const app = document.getElementById('app');
  C.loading(app, '正在训练随机森林与逻辑回归并计算阈值收益…');
  try {
    const d = await C.get('/api/loan');
    const o = d.overview;
    const m = d.metrics;
    const cm = m.confusion;

    const thresholdRows = d.thresholds.map(x => [
      Number(x.threshold).toFixed(2), C.pct(x.approval_pct), C.pct(x.bad_rate_pct),
      C.pct(x.default_recall_pct), C.money(x.expected_profit)
    ]);
    const importanceRows = d.feature_importance.map(x => [
      x.feature, Number(x.impurity).toFixed(3), Number(x.permutation_auc_drop).toFixed(3)
    ]);
    const segRows = (list, name) => list.map(x => [x.band, C.fmt(x.count), C.pct(x.default_pct)]);

    app.innerHTML = `
      <div class="page-head">
        <div class="eyebrow">Module 04 · Credit Risk</div>
        <h1>贷款违约：AUC 0.939 之后，阈值才是业务决策</h1>
        <p>5,000 条模拟信贷样本、7 个特征，违约率 15%。随机森林 AUC 0.939、逻辑回归 0.900、KS 0.735。模型排序能力只是上半场：按「好客户赚 2,000、坏客户亏 10,000」的成本假设，最优阈值在 0.25，而不是 0.5。</p>
      </div>

      ${C.kpis([
        { value: Number(o.auc_rf).toFixed(3), label: '随机森林 AUC', sub: `逻辑回归 ${Number(o.auc_lr).toFixed(3)} · 差距 ${(o.auc_rf - o.auc_lr).toFixed(3)}` },
        { value: Number(o.ks).toFixed(3), label: 'KS 统计量', sub: `PR-AUC ${Number(m.pr_auc).toFixed(3)}` },
        { value: o.best_threshold.toFixed(2), label: '收益最优阈值', sub: `通过率 ${C.pct(o.best_approval_pct)} · 坏账率 ${C.pct(o.best_bad_rate_pct)}` },
        { value: C.pct(o.default_rate), label: '样本违约率', sub: `${C.fmt(o.samples)} 条 · ${o.features} 个特征` },
        { value: `${Number(o.cv_mean).toFixed(3)} ± ${Number(o.cv_std).toFixed(3)}`, label: '5 折交叉验证 AUC', sub: `测试集 ${C.fmt(m.test_size)} 条` }
      ])}

      <div class="grid-2">
        ${C.panel('ROC 曲线', `随机森林 AUC 0.939，明显高于逻辑回归 0.900；差距来自「高负债 × 低信用」这类交互项。`, C.chartBox('rocChart', 'lg'))}
        ${C.panel('PR 曲线（更贴近不平衡业务）', `违约率只有 15%，PR-AUC ${m.pr_auc} 比 ROC 更能反映坏客户识别质量。默认阈值下精确率 ${C.pct(m.precision * 100)}、召回率 ${C.pct(m.recall * 100)}。`, C.chartBox('prChart', 'lg'))}
      </div>

      ${C.panel('阈值—收益权衡', `纵轴左侧是通过率/坏账率，右侧是测试集总期望收益。阈值 0.25 时通过率 83.8%、坏账率 3.9%，总期望收益最大；低于 0.25 虽然坏账更少，但拒绝太多好客户，总收益反而下降。`, C.chartBox('thresholdChart', 'lg') + C.table(['阈值', '通过率', '坏账率', '违约召回', '总期望收益'], thresholdRows, { note: '成本假设：好客户收益 2,000 元，坏客户损失 10,000 元；总期望收益 = 通过人数 × (好人占比 × 2000 − 坏人占比 × 10000)，在 1,000 条测试集上计算。' }))}

      <div class="grid-2">
        ${C.panel('概率校准', '校准曲线越接近对角线，模型输出越能直接当概率用。高分段预测概率与实际违约率基本贴合。', C.chartBox('calibChart'))}
        ${C.panel('混淆矩阵（阈值 0.5）', `默认阈值下模型非常保守：只抓出 ${C.fmt(cm.tp)} 个坏客户，漏掉 ${C.fmt(cm.fn)} 个；精确率高但召回率只有 45%。这正是需要下调阈值的原因。`, `
          <div class="cm-grid">
            <div class="cm-label"></div><div class="cm-label">预测：正常</div><div class="cm-label">预测：违约</div>
            <div class="cm-label">实际：正常</div><div class="cm-cell good"><b>${C.fmt(cm.tn)}</b><span>TN</span></div><div class="cm-cell bad"><b>${C.fmt(cm.fp)}</b><span>FP</span></div>
            <div class="cm-label">实际：违约</div><div class="cm-cell bad"><b>${C.fmt(cm.fn)}</b><span>FN · 漏放</span></div><div class="cm-cell good"><b>${C.fmt(cm.tp)}</b><span>TP</span></div>
          </div>
          ${C.table(['指标', '数值'], [
            ['准确率 Accuracy', C.pct(m.accuracy * 100)],
            ['精确率 Precision', C.pct(m.precision * 100)],
            ['召回率 Recall', C.pct(m.recall * 100)],
            ['F1', Number(m.f1).toFixed(3)],
            ['预测违约率', C.pct(m.default_rate_pred)]
          ])}`)}
      </div>

      <div class="grid-2">
        ${C.panel('特征重要性', 'debt_ratio 同时是树模型不纯度和置换重要性的第一名；置换重要性把「模型依赖」与「单特征信息量」分开看。', C.chartBox('impChart', 'lg') + C.table(['特征', '不纯度重要性', '置换后 AUC 下降'], importanceRows, { note: '置换重要性 = 打乱该特征后 AUC 的下降幅度，越大说明模型越依赖它。' }))}
        ${C.panel('交叉验证稳定性', `5 折 AUC ${Number(o.cv_mean).toFixed(4)} ± ${Number(o.cv_std).toFixed(4)}，波动很小，说明模型没有依赖某一次切分。`, C.chartBox('cvChart'))}
      </div>

      ${C.panel('分群违约率：风险不是线性的', '信用分越低、负债率越高，违约率单调上升；但真正陡峭的是「低信用 + 高负债」的交叉区域，这也是树模型优于线性模型的原因。', `
        <div class="grid-2">
          ${C.chartBox('segCredit')}
          ${C.chartBox('segDebt')}
        </div>
        <div class="grid-2">
          ${C.table(['信用分区间', '样本数', '违约率'], segRows(d.segments.credit))}
          ${C.table(['负债率区间', '样本数', '违约率'], segRows(d.segments.debt))}
        </div>`)}
    `;

    // ROC
    C.chart('rocChart', {
      grid: { left: 18, right: 44, top: 34, bottom: 18, containLabel: true },
      legend: { top: 2 },
      tooltip: { trigger: 'axis', valueFormatter: v => Number(v).toFixed(3) },
      xAxis: C.valAxis({ min: 0, max: 1, name: 'FPR' }),
      yAxis: C.valAxis({ min: 0, max: 1, name: 'TPR' }),
      series: [
        { name: '随机森林', type: 'line', smooth: true, symbol: 'none', lineStyle: { width: 3, color: '#22d3ee' }, areaStyle: { color: 'rgba(34,211,238,.07)' }, data: d.roc.map(x => [x.fpr, x.tpr]) },
        { name: '随机猜测', type: 'line', symbol: 'none', lineStyle: { width: 1, type: 'dashed', color: '#64748b' }, data: [[0, 0], [1, 1]] }
      ]
    });

    // PR
    C.chart('prChart', {
      grid: { left: 18, right: 44, top: 34, bottom: 18, containLabel: true },
      tooltip: { trigger: 'axis', valueFormatter: v => Number(v).toFixed(3) },
      xAxis: C.valAxis({ min: 0, max: 1, name: 'Recall' }),
      yAxis: C.valAxis({ min: 0, max: 1, name: 'Precision' }),
      series: [{
        name: 'PR 曲线', type: 'line', smooth: true, symbol: 'none',
        lineStyle: { width: 3, color: '#8b5cf6' },
        areaStyle: { color: 'rgba(139,92,246,.12)' },
        data: d.pr.map(x => [x.recall, x.precision])
      }]
    });

    // 阈值
    C.chart('thresholdChart', {
      grid: { left: 18, right: 54, top: 40, bottom: 16, containLabel: true },
      legend: { top: 2 },
      tooltip: { trigger: 'axis' },
      xAxis: C.catAxis(d.thresholds.map(x => Number(x.threshold).toFixed(2))),
      yAxis: [
        C.valAxis({ min: 0, max: 100, name: '%', nameGap: 16, axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}%' } }),
        C.valAxis({ min: 0, name: '元', nameGap: 18, splitLine: { show: false }, axisLabel: { color: '#94a3b8', fontSize: 11 } })
      ],
      series: [
        { name: '通过率', type: 'bar', barWidth: '42%', itemStyle: { borderRadius: [4, 4, 0, 0], color: 'rgba(34,211,238,.5)' }, data: d.thresholds.map(x => x.approval_pct) },
        { name: '坏账率', type: 'line', symbol: 'none', smooth: true, lineStyle: { width: 2.5, color: '#fb7185' }, itemStyle: { color: '#fb7185' }, data: d.thresholds.map(x => x.bad_rate_pct) },
        {
          name: '总期望收益', type: 'line', yAxisIndex: 1, symbol: 'none', smooth: true,
          lineStyle: { width: 3, color: '#f59e0b' }, itemStyle: { color: '#f59e0b' },
          data: d.thresholds.map(x => x.expected_profit),
          markLine: {
            silent: true, symbol: 'none',
            lineStyle: { color: 'rgba(245,158,11,.65)', type: 'dashed' },
            label: { color: '#f59e0b', fontSize: 10, formatter: '最优阈值' },
            data: [{ xAxis: String(o.best_threshold) }]
          }
        }
      ]
    });

    // 校准
    C.chart('calibChart', {
      grid: { left: 34, right: 44, top: 34, bottom: 18, containLabel: true },
      legend: { top: 2 },
      tooltip: { trigger: 'axis', valueFormatter: v => v + '%' },
      xAxis: C.valAxis({ min: 0, max: 100, name: '预测违约率%' }),
      yAxis: C.valAxis({ min: 0, max: 100, name: '实际违约率%' }),
      series: [
        { name: '校准曲线', type: 'line', symbolSize: 7, lineStyle: { width: 3, color: '#34d399' }, itemStyle: { color: '#34d399' }, data: d.calibration.map(x => [x.predicted_pct, x.actual_pct]) },
        { name: '完美校准', type: 'line', symbol: 'none', lineStyle: { width: 1, type: 'dashed', color: '#64748b' }, data: [[0, 0], [100, 100]] }
      ]
    });

    // 重要性
    const imp = [...d.feature_importance].sort((a, b) => a.permutation_auc_drop - b.permutation_auc_drop);
    C.chart('impChart', {
      grid: { left: 18, right: 46, top: 16, bottom: 10, containLabel: true },
      tooltip: {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: p => {
          const x = imp[p[0].dataIndex];
          return `<b>${x.feature}</b><br/>置换后 AUC 下降：${x.permutation_auc_drop}<br/>不纯度重要性：${x.impurity}`;
        }
      },
      xAxis: C.valAxis(),
      yAxis: C.catAxis(imp.map(x => x.feature), { axisLabel: { color: '#cbd5e1', fontSize: 11 } }),
      series: [{
        type: 'bar', data: imp.map(x => x.permutation_auc_drop), barWidth: '56%',
        itemStyle: { borderRadius: [0, 6, 6, 0], color: C.gradient('#8b5cf6', false) },
        label: { show: true, position: 'right', color: '#94a3b8', fontSize: 10, formatter: '{c}' }
      }]
    });

    // CV
    C.chart('cvChart', {
      grid: { left: 18, right: 24, top: 28, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `第 ${p[0].axisValue} 折<br/>AUC：<b>${p[0].value}</b>` },
      xAxis: C.catAxis(d.cv_scores.map((_, i) => `Fold ${i + 1}`)),
      yAxis: C.valAxis({ min: 0.9, max: 0.96 }),
      series: [{
        type: 'bar', data: d.cv_scores, barWidth: '42%',
        itemStyle: { borderRadius: [5, 5, 0, 0], color: C.gradient('#22d3ee') },
        label: { show: true, position: 'top', color: '#94a3b8', fontSize: 10 },
        markLine: {
          silent: true, symbol: 'none',
          lineStyle: { color: 'rgba(245,158,11,.7)', type: 'dashed' },
          label: { color: '#f59e0b', fontSize: 10, formatter: `均值 ${o.cv_mean}` },
          data: [{ yAxis: o.cv_mean }]
        }
      }]
    });

    // 分群
    const segChart = (id, list, color) => C.chart(id, {
      grid: { left: 18, right: 20, top: 30, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>违约率：<b>${p[0].value}%</b><br/>样本：${C.fmt(list[p[0].dataIndex].count)}` },
      xAxis: C.catAxis(list.map(x => x.band)),
      yAxis: C.valAxis({ axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}%' } }),
      series: [{
        type: 'bar', data: list.map(x => x.default_pct), barWidth: '50%',
        itemStyle: { borderRadius: [5, 5, 0, 0], color: C.gradient(color) },
        label: { show: true, position: 'top', color: '#94a3b8', fontSize: 10, formatter: '{c}%' }
      }]
    });
    segChart('segCredit', d.segments.credit, '#fb7185');
    segChart('segDebt', d.segments.debt, '#8b5cf6');
  } catch (e) {
    C.error(app, e);
  }
})();
