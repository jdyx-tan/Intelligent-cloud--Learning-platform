export default {
  development: {
    // 开发环境接口请求
    host: 'http://api.tianji.com',
    aiHost: '/ais-local',
    // host: '/api',
    // 开发环境 cdn 路径
    cdn: '',
  },
  test: {
    // 测试环境接口地址
    host: 'http://api.tianji.com',
    aiHost: 'http://api.tianji.com/ais',
    // 测试环境 cdn 路径
    cdn: '',
  },
  product: {
    // 正式环境接口地址
    host: 'http://api.tianji.com',
    aiHost: 'http://api.tianji.com/ais',
    // 正式环境 cdn 路径
    cdn: '',
  },
};
