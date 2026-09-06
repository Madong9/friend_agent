const api = require('../../services/api.js');

Page({
  data: {
    partner: null,
    sharedInterests: [],
    icebreakerTip: '',
    demoMatch: false,
  },

  onLoad() {
    const stored = wx.getStorageSync('matchDetailPartner');
    if (!stored) {
      return;
    }
    const partner = stored.partner || stored;
    this.setData({
      partner,
      demoMatch: stored.demo_match || false,
      icebreakerTip: '可以先从校园生活聊起，比如最近课表、食堂或者社团。',
    });
    api.getMe().then(
      (me) => {
        const mine = me.interests || [];
        const theirs = partner.interests || [];
        const shared = mine.filter((tag) => theirs.indexOf(tag) !== -1);
        const tip = shared.length > 0
          ? '看到你也喜欢' + shared.join('、') + '，可以问问平时一般在哪玩、要不要一起。'
          : this.data.icebreakerTip;
        this.setData({
          sharedInterests: shared,
          icebreakerTip: tip,
        });
      },
      (err) => wx.showToast({ title: err.message, icon: 'none' })
    );
  },

  onBlock() {
    if (!this.data.partner) {
      return;
    }
    wx.showModal({
      title: '确认拉黑',
      content: '拉黑后你们双方都不会再被推荐给对方。',
      success: (res) => {
        if (res.confirm) {
          api.blockUser(this.data.partner.id).then(
            () => {
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

  goChat() {
    if (!this.data.partner || this.data.demoMatch) return;
    wx.setStorageSync('chatPartner', this.data.partner);
    wx.navigateTo({ url: '/pages/chat/chat' });
  },

  onReport() {
    if (!this.data.partner) {
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
          editable: true,
          placeholderText: '请简要说明，至少 2 个字',
          success: (res) => {
            if (!res.confirm || !(res.content || '').trim()) return;
            api.reportUser(this.data.partner.id, res.content, category.value).then(
              () => {
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
