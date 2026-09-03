const api = require('../../services/api.js');
const recommendations = require('../../services/recommendations.js');

Page({
  data: {
    mutualMatches: [],
    queue: [],
    myInterests: [],
    loading: false,
  },

  onShow() {
    this.load();
  },

  load() {
    this.setData({ queue: recommendations.getLatest() });
    api.getMe().then((me) => {
      this.setData({ myInterests: me.interests || [] });
    }, (err) => wx.showToast({ title: err.message, icon: 'none' }));
    api.getMatches().then(
      (matches) => {
        this.setData({ mutualMatches: matches || [] });
      },
      () => {
        this.setData({ mutualMatches: [] });
      }
    );
  },

  onLike(e) {
    this.feedback(e.detail.candidateId, 'LIKE');
  },

  onPass(e) {
    this.feedback(e.detail.candidateId, 'PASS');
  },

  onNotRelevant(e) {
    this.feedback(e.detail.candidateId, 'NOT_RELEVANT');
  },

  feedback(candidateId, feedback) {
    if (this.data.loading) {
      return;
    }
    this.setData({ loading: true });
    api.sendFeedback(candidateId, feedback).then(
      (result) => {
        const queue = recommendations.removeCandidate(candidateId);
        this.setData({ queue, loading: false });
        if (result.matched) {
          wx.showToast({ title: '互相匹配成功！', icon: 'success' });
        } else {
          wx.showToast({ title: '已记录反馈', icon: 'none' });
        }
        api.getMatches().then((matches) => {
          this.setData({ mutualMatches: matches || [] });
        });
      },
      (err) => {
        this.setData({ loading: false });
        wx.showToast({ title: err.message, icon: 'none' });
      }
    );
  },

  goCandidateDetail(e) {
    const candidateId = e.detail.candidateId;
    const candidate = this.data.queue.find((item) => item.id === candidateId);
    if (!candidate) {
      return;
    }
    wx.setStorageSync('matchDetailCandidate', candidate);
    wx.navigateTo({ url: '/pages/match-detail/match-detail' });
  },

  goMatched(e) {
    const partnerId = e.currentTarget.dataset.partner;
    const item = this.data.mutualMatches.find(
      (match) => match.partner.id === partnerId
    );
    if (item) {
      wx.setStorageSync('matchDetailPartner', {
        partner: item.partner,
        demo_match: item.demo_match || false,
      });
    }
    wx.navigateTo({ url: '/pages/matched/matched' });
  },
});
