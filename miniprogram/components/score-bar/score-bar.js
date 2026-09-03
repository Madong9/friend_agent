// components/score-bar — 可解释匹配分数条（含用户主动同意后的性格兼容度）
Component({
  properties: {
    features: { type: Object, value: {} },
  },
  data: {
    rows: [],
  },
  observers: {
    features: function (features) {
      const labels = {
        interest: '兴趣',
        activity: '活动',
        availability: '时间',
        social_goal: '社交目标',
        location: '校区',
        feedback: '反馈',
        personality: '社交风格',
      };
      const rows = [];
      Object.keys(labels).forEach((key) => {
        const value = features[key];
        if (typeof value === 'number') {
          rows.push({
            key,
            label: labels[key],
            percent: Math.round(value * 100),
          });
        }
      });
      this.setData({ rows });
    },
  },
  methods: {},
});
