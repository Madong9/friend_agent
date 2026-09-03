const api = require('../../services/api.js');
const recommendations = require('../../services/recommendations.js');

Page({
  data: {
    candidate: null,
    totalPercent: 0,
    feedbackLoading: false,
  },

  onLoad() {
    const candidate = wx.getStorageSync('matchDetailCandidate');
    if (candidate) {
      const total = candidate.total || 0;
      this.setData({
        candidate,
        totalPercent: Math.round(total * 100),
      });
    }
  },

  onLike() {
    return this.submitFeedback('LIKE');
  },

  onPass() {
    return this.submitFeedback('PASS');
  },

  onNotRelevant() {
    return this.submitFeedback('NOT_RELEVANT');
  },

  submitFeedback(feedback) {
    const candidate = this.data.candidate;
    if (!candidate || this.data.feedbackLoading) {
      return Promise.resolve();
    }
    this.setData({ feedbackLoading: true });
    return api.sendFeedback(candidate.id, feedback).then(
      (result) => {
        recommendations.removeCandidate(candidate.id);
        this.setData({ feedbackLoading: false });
        let title = '已记录反馈';
        if (feedback === 'LIKE') {
          if (result && result.matched) {
            title = result.demo_match ? '测试匹配成功' : '互相匹配成功！';
          } else {
            title = '已表达兴趣';
          }
        } else if (feedback === 'PASS') {
          title = '已跳过';
        } else if (feedback === 'NOT_RELEVANT') {
          title = '已减少此类推荐';
        }
        wx.showToast({ title, icon: feedback === 'LIKE' ? 'success' : 'none' });
        wx.navigateBack();
        return result;
      },
      (err) => {
        this.setData({ feedbackLoading: false });
        wx.showToast({ title: err.message, icon: 'none' });
        return null;
      }
    );
  },

  onBlock() {
    if (!this.data.candidate) {
      return;
    }
    wx.showModal({
      title: '确认拉黑',
      content: '拉黑后你们双方都不会再被推荐给对方。',
      success: (res) => {
        if (res.confirm) {
          api.blockUser(this.data.candidate.id).then(
            () => {
              recommendations.removeCandidate(this.data.candidate.id);
              wx.showToast({ title: '已拉黑', icon: 'success' });
              wx.navigateBack();
            },
            (err) => {
              wx.showToast({ title: err.message, icon: 'none' });
            }
          );
        }
      },
    });
  },

  onReport() {
    if (!this.data.candidate) {
      return;
    }
    const categories = [
      { label: '骚扰或辱骂', value: 'HARASSMENT' },
      { label: '诈骗或引流', value: 'FRAUD' },
      { label: '虚假身份', value: 'FAKE_IDENTITY' },
      { label: '不当内容', value: 'INAPPROPRIATE_CONTENT' },
      { label: '其他', value: 'OTHER' },
    ];
    wx.showActionSheet({
      itemList: categories.map((item) => item.label),
      success: (choice) => {
        const category = categories[choice.tapIndex];
        wx.showModal({
          title: category.label,
          content: '',
          editable: true,
          placeholderText: '请简要说明，至少 2 个字',
          success: (res) => {
            if (!res.confirm || !(res.content || '').trim()) return;
            api.reportUser(this.data.candidate.id, res.content, category.value).then(
              () => {
                recommendations.removeCandidate(this.data.candidate.id);
                wx.showToast({ title: '已提交举报', icon: 'success' });
                wx.navigateBack();
              },
              (err) => wx.showToast({ title: err.message, icon: 'none' })
            );
          },
        });
      },
    });
  },
});
