import axios from 'axios';
import proxy from '../config/proxy';
import { ElMessage, ElMessageBox } from 'element-plus';
import  router  from '../router';
import {ref} from "vue";
import {tryRefreshToken} from './refreshToken'

const env = import.meta.env.MODE || 'development';
const host = env === 'mock' ? 'https://mock.boxuegu.com/mock/3359' : proxy[env].host; // 如果是mock模式 就不配置host 会走本地Mock拦截
const aiHost = proxy[env].aiHost || '/ais-local';
const CODE = {
  LOGIN_TIMEOUT: 1000,
  REQUEST_SUCCESS: 200,
  REQUEST_FOBID: 1001,
};
// 登录异常弹窗处理
let isLogin = true
// 刷新标记
// let refreshing = ref(false)

const instance = axios.create({
  baseURL:  host, // 'http://172.17.2.134/api-test',
  timeout: 60000,
  withCredentials: false,
});

const aiInstance = axios.create({
  baseURL: aiHost,
  timeout: 60000,
  withCredentials: false,
});

const applyCommonHeaders = (config, includeUserInfo = false) => {
  const TOKEN = sessionStorage.getItem('token');
  const storedUserInfo = sessionStorage.getItem('userInfo');
  let userInfo = null;
  try {
    userInfo = storedUserInfo ? JSON.parse(storedUserInfo) : null;
  } catch (e) {
    userInfo = null;
  }
  const userId = userInfo?.id || (env === 'development' ? 2 : undefined);
  config.headers = {
    ...config.headers,
    "Content-Type": "application/json",
    "authorization": TOKEN
  };
  if (includeUserInfo && userId !== undefined && userId !== null && userId !== '') {
    config.headers['user-info'] = String(userId);
  }
  return config;
};

instance.interceptors.request.use((config) => {
  return applyCommonHeaders(config, false)
});

aiInstance.interceptors.request.use((config) => {
  return applyCommonHeaders(config, true)
});

// instance.defaults.timeout = 20000;
async function refreshToken(err){
  // 尝试刷新token
  let success = await tryRefreshToken();
  if(success){
    // refreshing.value = false;
    return instance(err.config);
  }
  // refreshing.value = false;
  ElMessageBox.alert(
    '请先登录！',
    '未登录或登录超时',
    {
      confirmButtonText: '重新登录',
      callback: () => {
        router.push('/login')
      },
    }
  )
  return true;
}
function alertLoginMessage() {
  isLogin = false;
  sessionStorage.removeItem('userInfo');
  sessionStorage.removeItem("token");
  ElMessageBox.confirm(
    '您的账号登录超时或在其他机器登录，请重新登录或更换账号登录！',
    '登录超时',
    {
      confirmButtonText: '重新登录',
      cancelButtonText: '继续浏览',
      type: 'warning',
    }
    )
    .then(() => {
      router.push('/login')
    })
    .catch(() => {
      router.go(0)
    })
}
// const sleep = (delay) => new Promise((resolve) => setTimeout(resolve, delay))
const handleResponse = async (response) => {
  // 1.获取业务状态码
  let code = response.data.code;
  // 2.业务状态码为200，直接返回
  if (code === CODE.REQUEST_SUCCESS || code === undefined) {
    return response.data;
  }

  // 3.业务状态码为401，代表未登录
  if (code === 401 && isLogin) {
    isLogin = false;
    alertLoginMessage();
  }

  return response.data;
/*    // 4.业务状态码为其它，返回异常
  ElMessage({
    message: response.data.msg,
    type: 'error'
  });
  throw new Error(response.data.msg);*/
};

const handleAiResponse = async (response) => {
  const payload = response.data;
  if (payload && typeof payload === 'object' && 'code' in payload) {
    return handleResponse(response);
  }
  return {
    code: CODE.REQUEST_SUCCESS,
    msg: 'OK',
    data: payload,
  };
};

const handleError = async (err) => {
  if(err.response?.status === 401 && isLogin){
    // 登录异常或超时，刷新token
    return refreshToken(err);
  }
  // refreshing = false;
  return Promise.reject(err);
};

instance.interceptors.response.use(handleResponse, handleError);
aiInstance.interceptors.response.use(handleAiResponse, handleError);

export { aiInstance };
export default instance;
