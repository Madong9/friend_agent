const api = require('../../services/api.js');

const REQUEST_STATUS_LABELS = {
  OPEN: '等待新候选',
  PAUSED: '已暂停',
  FULFILLED: '已找到候选',
  EXPIRED: '已过期',
};

function normalizeRequest(item) {
  const intent = item && item.intent && typeof item.intent === 'object'
    ? item.intent
    : {};
  const availability = Array.isArray(intent.availability)
    ? intent.availability
    : [];
  const status = String((item && item.status) || '').toUpperCase();
  return {
    ...item,
    intent,
    status,
    statusLabel: REQUEST_STATUS_LABELS[status] || status || '未知状态',
    availabilityText: availability.join('、'),
    canToggle: status === 'OPEN' || status === 'PAUSED',
  };
}

Page({
  data: {
    notifications: [],
    requests: [],
    loading: false,
    notificationsLoaded: false,
    requestsLoaded: false,
    notificationError: '',
    requestError: '',
    actionRequestId: null,
  },

  onShow() {
    this.load();
  },

  load() {
    this.setData({
      loading: true,
      notificationError: '',
      requestError: '',
    });
    const settled = (promise) =>
      promise.then(
        (value) => ({ ok: true, value }),
        (error) => ({ ok: false, error })
      );
    return Promise.all([
      settled(api.getNotifications(false)),
      settled(api.getPartnerRequests()),
    ]).then(([notificationResult, requestResult]) => {
      const next = { loading: false };
      if (notificationResult.ok) {
        next.notifications = Array.isArray(notificationResult.value)
          ? notificationResult.value
          : [];
        next.notificationsLoaded = true;
      } else {
        next.notificationError =
          (notificationResult.error && notificationResult.error.message) ||
          '通知加载失败';
        next.notificationsLoaded = false;
      }
      if (requestResult.ok) {
        const requests = Array.isArray(requestResult.value)
          ? requestResult.value
          : [];
        next.requests = requests.map(normalizeRequest);
        next.requestsLoaded = true;
      } else {
        next.requestError =
          (requestResult.error && requestResult.error.message) ||
          '找搭子需求加载失败';
        next.requestsLoaded = false;
      }
      this.setData(next);
    });
  },

  readNotification(e) {
    api.markNotificationRead(e.currentTarget.dataset.id).then(
      () => this.load(),
      (err) => wx.showToast({ title: err.message, icon: 'none' })
    );
  },

  toggleRequest(e) {
    const item = this.data.requests.find(
      (request) => String(request.id) === String(e.currentTarget.dataset.id)
    );
    if (!item || !item.canToggle || this.data.actionRequestId !== null) return;
    this.setData({ actionRequestId: item.id });
    api
      .updatePartnerRequest(item.id, item.status === 'PAUSED' ? 'OPEN' : 'PAUSED')
      .then(
        () => this.load().then(() => this.setData({ actionRequestId: null })),
        (err) => {
          this.setData({ actionRequestId: null });
          wx.showToast({ title: err.message, icon: 'none' });
        }
      );
  },
});
