export async function request(path, body) {
  const response = await fetch(`/api/${path}`, body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data;
  try { data = await response.json(); }
  catch { throw new Error("无法读取服务响应，请确认后端已启动并加载最新代码。"); }
  if (!response.ok) throw new Error(data.error || "本轮请求失败，请重试。");
  return data;
}

export function getState(scriptId) {
  return request(`state?${new URLSearchParams({ scriptId })}`);
}
