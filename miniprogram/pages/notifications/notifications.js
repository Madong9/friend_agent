const api = require('../../services/api.js');

Page({
  data: {
    notifications: [],
    requests: [],
    loading: false,
    notificationsLoaded: false,
    requestsLoaded: false,
    notificationError: '',
    requestError: '',
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
        next.requests = requests.map((item) => ({
          ...item,
          availabilityText: (
            (item.intent && item.intent.availability) ||
            []
          ).join('、'),
        }));
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
    api.markNotificationRead(e.currentTarget.dataset.id).then(() => this.load());
  },

  toggleRequest(e) {
    const item = this.data.requests.find(
      (request) => request.id === e.currentTarget.dataset.id
    );
    if (!item) return;
    api
      .updatePartnerRequest(item.id, item.status === 'PAUSED' ? 'OPEN' : 'PAUSED')
      .then(() => this.load());
  },
});
