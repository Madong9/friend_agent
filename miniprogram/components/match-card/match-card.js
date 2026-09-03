// components/match-card — 候选卡片：公开信息 + 分数 + 反馈按钮
Component({
  properties: {
    candidate: { type: Object, value: {} },
    myInterests: { type: Array, value: [] },
    feedbackDisabled: { type: Boolean, value: false },
  },
  data: {
    sharedInterests: [],
    scorePercent: 0,
  },
  observers: {
    'candidate, myInterests': function (candidate, myInterests) {
      const clean = (values) => (values || [])
        .map((value) => String(value || '').trim())
        .filter(Boolean);
      const mine = clean(myInterests);
      const theirs = clean(candidate && candidate.interests);
      const total = candidate && candidate.total ? candidate.total : 0;
      this.setData({
        sharedInterests: mine.filter((tag) => theirs.indexOf(tag) !== -1),
        scorePercent: Math.round(total * 100),
      });
    },
  },
  methods: {
    onDetail() {
      this.triggerEvent('detail', { candidateId: this.data.candidate.id });
    },
    onLike() {
      this.triggerEvent('like', { candidateId: this.data.candidate.id });
    },
    onPass() {
      this.triggerEvent('pass', { candidateId: this.data.candidate.id });
    },
    onNotRelevant() {
      this.triggerEvent('notrelevant', { candidateId: this.data.candidate.id });
    },
  },
});
