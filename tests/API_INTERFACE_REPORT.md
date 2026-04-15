# 🔍 前后端 API 接口匹配度检查报告

**生成时间**: 2026-04-10 10:25:03
**项目路径**: D:\Explore\ollma

## 📊 统计概览

| 指标 | 数量 |
|------|------|
| 前端 API 调用 | 12 |
| 后端 API 定义 | 101 |
| 不匹配项 | 91 |

## 🔴 严重 问题 (9 个)

### 1. API 未实现

**问题描述**: 前端调用 /api/tags，但后端无此接口

**前端位置**: `web\js\api\api.js:199`
**前端调用**: `{'POST'} /api/tags`

**建议**: 后端需要实现此接口，或前端移除调用

---

### 2. API 未实现

**问题描述**: 前端调用 /api/generate，但后端无此接口

**前端位置**: `web\js\api\api.js:199`
**前端调用**: `{'POST'} /api/generate`

**建议**: 后端需要实现此接口，或前端移除调用

---

### 3. API 未实现

**问题描述**: 前端调用 /api/tags，但后端无此接口

**前端位置**: `web\js\api\api.js:260`
**前端调用**: `{'GET'} /api/tags`

**建议**: 后端需要实现此接口，或前端移除调用

---

### 4. API 未实现

**问题描述**: 前端调用 /api/version，但后端无此接口

**前端位置**: `web\js\api\api.js:274`
**前端调用**: `{'GET'} /api/version`

**建议**: 后端需要实现此接口，或前端移除调用

---

### 5. API 未实现

**问题描述**: 前端调用 /api/show，但后端无此接口

**前端位置**: `web\js\api\api.js:404`
**前端调用**: `{'GET'} /api/show`

**建议**: 后端需要实现此接口，或前端移除调用

---

### 6. API 未实现

**问题描述**: 前端调用 /api/delete，但后端无此接口

**前端位置**: `web\js\api\api.js:497`
**前端调用**: `{'DELETE'} /api/delete`

**建议**: 后端需要实现此接口，或前端移除调用

---

### 7. API 未实现

**问题描述**: 前端调用 /api/copy，但后端无此接口

**前端位置**: `web\js\api\api.js:510`
**前端调用**: `{'GET'} /api/copy`

**建议**: 后端需要实现此接口，或前端移除调用

---

### 8. API 未实现

**问题描述**: 前端调用 /api/embeddings，但后端无此接口

**前端位置**: `web\js\api\api.js:862`
**前端调用**: `{'GET'} /api/embeddings`

**建议**: 后端需要实现此接口，或前端移除调用

---

### 9. API 未实现

**问题描述**: 前端调用 /api/search，但后端无此接口

**前端位置**: `web\js\api\unified_client.js:267`
**前端调用**: `{'GET'} /api/search`

**建议**: 后端需要实现此接口，或前端移除调用

---

## 🟠 高 问题 (1 个)

### 1. HTTP 方法不匹配

**问题描述**: 前端调用 GET，但后端只支持 {'POST'}

**前端位置**: `web\js\api\unified_client.js:267`
**前端调用**: `{'GET'} /api/chat`
**后端位置**: `server\api\chat.py:262`
**后端定义**: `{'POST'} /api/chat`

**建议**: 统一使用 {'POST'} 方法，或后端添加 GET 支持

---

## 🟢 低 问题 (81 个)

### 1. API 未被前端使用

**问题描述**: 后端定义了 /api/api-key/generate，但前端未调用

**后端位置**: `server\api\api_key.py:32`
**后端定义**: `{'POST'} /api/api-key/generate`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 2. API 未被前端使用

**问题描述**: 后端定义了 /api/api-key/list，但前端未调用

**后端位置**: `server\api\api_key.py:60`
**后端定义**: `{'GET'} /api/api-key/list`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 3. API 未被前端使用

**问题描述**: 后端定义了 /api/api-key/revoke，但前端未调用

**后端位置**: `server\api\api_key.py:82`
**后端定义**: `{'POST'} /api/api-key/revoke`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 4. API 未被前端使用

**问题描述**: 后端定义了 /api/api-key/update，但前端未调用

**后端位置**: `server\api\api_key.py:112`
**后端定义**: `{'POST'} /api/api-key/update`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 5. API 未被前端使用

**问题描述**: 后端定义了 /api/api-key/verify，但前端未调用

**后端位置**: `server\api\api_key.py:144`
**后端定义**: `{'POST'} /api/api-key/verify`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 6. API 未被前端使用

**问题描述**: 后端定义了 /api/asr/transcribe，但前端未调用

**后端位置**: `server\api\asr.py:69`
**后端定义**: `{'POST'} /api/asr/transcribe`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 7. API 未被前端使用

**问题描述**: 后端定义了 /api/voice/transcribe，但前端未调用

**后端位置**: `server\api\asr.py:70`
**后端定义**: `{'POST'} /api/voice/transcribe`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 8. API 未被前端使用

**问题描述**: 后端定义了 /api/whisper/model，但前端未调用

**后端位置**: `server\api\asr.py:103`
**后端定义**: `{'GET'} /api/whisper/model`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 9. API 未被前端使用

**问题描述**: 后端定义了 /v1/chat/completions，但前端未调用

**后端位置**: `server\api\chat.py:402`
**后端定义**: `{'POST'} /v1/chat/completions`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 10. API 未被前端使用

**问题描述**: 后端定义了 /v1/completions，但前端未调用

**后端位置**: `server\api\chat.py:403`
**后端定义**: `{'POST'} /v1/completions`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 11. API 未被前端使用

**问题描述**: 后端定义了 /api/context/config，但前端未调用

**后端位置**: `server\api\context.py:102`
**后端定义**: `{'GET', 'OPTIONS'} /api/context/config`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 12. API 未被前端使用

**问题描述**: 后端定义了 /api/context/config，但前端未调用

**后端位置**: `server\api\context.py:114`
**后端定义**: `{'OPTIONS', 'POST'} /api/context/config`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 13. API 未被前端使用

**问题描述**: 后端定义了 /api/context/config/reset，但前端未调用

**后端位置**: `server\api\context.py:142`
**后端定义**: `{'OPTIONS', 'POST'} /api/context/config/reset`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 14. API 未被前端使用

**问题描述**: 后端定义了 /api/context/clear，但前端未调用

**后端位置**: `server\api\context.py:166`
**后端定义**: `{'OPTIONS', 'POST'} /api/context/clear`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 15. API 未被前端使用

**问题描述**: 后端定义了 /api/functions/list，但前端未调用

**后端位置**: `server\api\functions.py:32`
**后端定义**: `{'GET'} /api/functions/list`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 16. API 未被前端使用

**问题描述**: 后端定义了 /api/functions/execute，但前端未调用

**后端位置**: `server\api\functions.py:46`
**后端定义**: `{'POST'} /api/functions/execute`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 17. API 未被前端使用

**问题描述**: 后端定义了 /api/functions/history，但前端未调用

**后端位置**: `server\api\functions.py:90`
**后端定义**: `{'GET'} /api/functions/history`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 18. API 未被前端使用

**问题描述**: 后端定义了 /api/assistant/computer，但前端未调用

**后端位置**: `server\api\functions.py:106`
**后端定义**: `{'POST'} /api/assistant/computer`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 19. API 未被前端使用

**问题描述**: 后端定义了 /api/assistant/computer/execute，但前端未调用

**后端位置**: `server\api\functions.py:126`
**后端定义**: `{'POST'} /api/assistant/computer/execute`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 20. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/stream，但前端未调用

**后端位置**: `server\api\group_chat.py:77`
**后端定义**: `{'GET'} /api/group_chat/stream`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 21. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/characters，但前端未调用

**后端位置**: `server\api\group_chat.py:150`
**后端定义**: `{'GET', 'POST'} /api/group_chat/characters`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 22. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/auto_chat/start，但前端未调用

**后端位置**: `server\api\group_chat.py:183`
**后端定义**: `{'POST'} /api/group_chat/auto_chat/start`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 23. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/auto_chat/pause，但前端未调用

**后端位置**: `server\api\group_chat.py:202`
**后端定义**: `{'POST'} /api/group_chat/auto_chat/pause`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 24. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/auto_chat/resume，但前端未调用

**后端位置**: `server\api\group_chat.py:211`
**后端定义**: `{'POST'} /api/group_chat/auto_chat/resume`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 25. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/auto_chat/stop，但前端未调用

**后端位置**: `server\api\group_chat.py:220`
**后端定义**: `{'POST'} /api/group_chat/auto_chat/stop`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 26. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/messages，但前端未调用

**后端位置**: `server\api\group_chat.py:227`
**后端定义**: `{'GET'} /api/group_chat/messages`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 27. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/emotions，但前端未调用

**后端位置**: `server\api\group_chat.py:235`
**后端定义**: `{'GET'} /api/group_chat/emotions`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 28. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/viewpoints，但前端未调用

**后端位置**: `server\api\group_chat.py:242`
**后端定义**: `{'GET'} /api/group_chat/viewpoints`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 29. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/config，但前端未调用

**后端位置**: `server\api\group_chat.py:249`
**后端定义**: `{'POST'} /api/group_chat/config`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 30. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/world_setting，但前端未调用

**后端位置**: `server\api\group_chat.py:265`
**后端定义**: `{'GET'} /api/group_chat/world_setting`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 31. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/world_setting，但前端未调用

**后端位置**: `server\api\group_chat.py:280`
**后端定义**: `{'POST'} /api/group_chat/world_setting`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 32. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/clear，但前端未调用

**后端位置**: `server\api\group_chat.py:303`
**后端定义**: `{'POST'} /api/group_chat/clear`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 33. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/tts/synthesize，但前端未调用

**后端位置**: `server\api\group_chat.py:309`
**后端定义**: `{'POST'} /api/group_chat/tts/synthesize`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 34. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/message，但前端未调用

**后端位置**: `server\api\group_chat.py:350`
**后端定义**: `{'POST'} /api/group_chat/message`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 35. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/ask，但前端未调用

**后端位置**: `server\api\group_chat.py:374`
**后端定义**: `{'POST'} /api/group_chat/ask`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 36. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/summarize，但前端未调用

**后端位置**: `server\api\group_chat.py:394`
**后端定义**: `{'POST'} /api/group_chat/summarize`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 37. API 未被前端使用

**问题描述**: 后端定义了 /api/group_chat/models，但前端未调用

**后端位置**: `server\api\group_chat.py:410`
**后端定义**: `{'GET'} /api/group_chat/models`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 38. API 未被前端使用

**问题描述**: 后端定义了 /api/ollama/start，但前端未调用

**后端位置**: `server\api\health.py:109`
**后端定义**: `{'POST'} /api/ollama/start`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 39. API 未被前端使用

**问题描述**: 后端定义了 /api/cache/clear，但前端未调用

**后端位置**: `server\api\health.py:213`
**后端定义**: `{'POST'} /api/cache/clear`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 40. API 未被前端使用

**问题描述**: 后端定义了 /api/connection/reset，但前端未调用

**后端位置**: `server\api\health.py:263`
**后端定义**: `{'POST'} /api/connection/reset`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 41. API 未被前端使用

**问题描述**: 后端定义了 /api/image/models，但前端未调用

**后端位置**: `server\api\image.py:199`
**后端定义**: `{'GET'} /api/image/models`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 42. API 未被前端使用

**问题描述**: 后端定义了 /api/image/unload，但前端未调用

**后端位置**: `server\api\image.py:276`
**后端定义**: `{'POST'} /api/image/unload`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 43. API 未被前端使用

**问题描述**: 后端定义了 /api/image/memory，但前端未调用

**后端位置**: `server\api\image.py:304`
**后端定义**: `{'GET'} /api/image/memory`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 44. API 未被前端使用

**问题描述**: 后端定义了 /api/memory，但前端未调用

**后端位置**: `server\api\memory.py:39`
**后端定义**: `{'GET'} /api/memory`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 45. API 未被前端使用

**问题描述**: 后端定义了 /api/memory/list，但前端未调用

**后端位置**: `server\api\memory.py:40`
**后端定义**: `{'GET'} /api/memory/list`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 46. API 未被前端使用

**问题描述**: 后端定义了 /api/memory，但前端未调用

**后端位置**: `server\api\memory.py:59`
**后端定义**: `{'POST'} /api/memory`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 47. API 未被前端使用

**问题描述**: 后端定义了 /api/memory/<memory_id>，但前端未调用

**后端位置**: `server\api\memory.py:92`
**后端定义**: `{'GET'} /api/memory/<memory_id>`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 48. API 未被前端使用

**问题描述**: 后端定义了 /api/memory/<memory_id>，但前端未调用

**后端位置**: `server\api\memory.py:107`
**后端定义**: `{'PUT'} /api/memory/<memory_id>`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 49. API 未被前端使用

**问题描述**: 后端定义了 /api/memory/<memory_id>，但前端未调用

**后端位置**: `server\api\memory.py:128`
**后端定义**: `{'DELETE'} /api/memory/<memory_id>`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 50. API 未被前端使用

**问题描述**: 后端定义了 /api/memory/<memory_id>/delete，但前端未调用

**后端位置**: `server\api\memory.py:129`
**后端定义**: `{'POST'} /api/memory/<memory_id>/delete`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 51. API 未被前端使用

**问题描述**: 后端定义了 /api/memory/search，但前端未调用

**后端位置**: `server\api\memory.py:144`
**后端定义**: `{'GET', 'POST'} /api/memory/search`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 52. API 未被前端使用

**问题描述**: 后端定义了 /api/memory/related，但前端未调用

**后端位置**: `server\api\memory.py:145`
**后端定义**: `{'GET', 'POST'} /api/memory/related`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 53. API 未被前端使用

**问题描述**: 后端定义了 /api/memory/clear，但前端未调用

**后端位置**: `server\api\memory.py:177`
**后端定义**: `{'POST'} /api/memory/clear`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 54. API 未被前端使用

**问题描述**: 后端定义了 /api/models，但前端未调用

**后端位置**: `server\api\models.py:157`
**后端定义**: `{'GET'} /api/models`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 55. API 未被前端使用

**问题描述**: 后端定义了 /api/models/pull，但前端未调用

**后端位置**: `server\api\models.py:197`
**后端定义**: `{'POST'} /api/models/pull`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 56. API 未被前端使用

**问题描述**: 后端定义了 /v1/models，但前端未调用

**后端位置**: `server\api\models.py:241`
**后端定义**: `{'GET'} /v1/models`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 57. API 未被前端使用

**问题描述**: 后端定义了 /api/rag/retrieve，但前端未调用

**后端位置**: `server\api\rag.py:37`
**后端定义**: `{'POST'} /api/rag/retrieve`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 58. API 未被前端使用

**问题描述**: 后端定义了 /api/rag/reload，但前端未调用

**后端位置**: `server\api\rag.py:84`
**后端定义**: `{'POST'} /api/rag/reload`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 59. API 未被前端使用

**问题描述**: 后端定义了 /api/rag/clear-cache，但前端未调用

**后端位置**: `server\api\rag.py:98`
**后端定义**: `{'POST'} /api/rag/clear-cache`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 60. API 未被前端使用

**问题描述**: 后端定义了 /api/search/web，但前端未调用

**后端位置**: `server\api\search.py:24`
**后端定义**: `{'POST'} /api/search/web`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 61. API 未被前端使用

**问题描述**: 后端定义了 /api/search/instant，但前端未调用

**后端位置**: `server\api\search.py:45`
**后端定义**: `{'POST'} /api/search/instant`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 62. API 未被前端使用

**问题描述**: 后端定义了 /api/search/news，但前端未调用

**后端位置**: `server\api\search.py:70`
**后端定义**: `{'POST'} /api/search/news`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 63. API 未被前端使用

**问题描述**: 后端定义了 /api/search/clear-cache，但前端未调用

**后端位置**: `server\api\search.py:91`
**后端定义**: `{'POST'} /api/search/clear-cache`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 64. API 未被前端使用

**问题描述**: 后端定义了 /api/conversation，但前端未调用

**后端位置**: `server\api\summary.py:31`
**后端定义**: `{'POST'} /api/conversation`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 65. API 未被前端使用

**问题描述**: 后端定义了 /api/conversation/<conversation_id>/message，但前端未调用

**后端位置**: `server\api\summary.py:52`
**后端定义**: `{'POST'} /api/conversation/<conversation_id>/message`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 66. API 未被前端使用

**问题描述**: 后端定义了 /api/conversation/<conversation_id>/summary，但前端未调用

**后端位置**: `server\api\summary.py:79`
**后端定义**: `{'POST'} /api/conversation/<conversation_id>/summary`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 67. API 未被前端使用

**问题描述**: 后端定义了 /api/conversation/<conversation_id>/context，但前端未调用

**后端位置**: `server\api\summary.py:105`
**后端定义**: `{'GET'} /api/conversation/<conversation_id>/context`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 68. API 未被前端使用

**问题描述**: 后端定义了 /api/conversations，但前端未调用

**后端位置**: `server\api\summary.py:121`
**后端定义**: `{'GET'} /api/conversations`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 69. API 未被前端使用

**问题描述**: 后端定义了 /api/summary/generate，但前端未调用

**后端位置**: `server\api\summary.py:148`
**后端定义**: `{'POST'} /api/summary/generate`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 70. API 未被前端使用

**问题描述**: 后端定义了 /api/summary，但前端未调用

**后端位置**: `server\api\summary.py:175`
**后端定义**: `{'GET'} /api/summary`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 71. API 未被前端使用

**问题描述**: 后端定义了 /api/summary/<summary_id>，但前端未调用

**后端位置**: `server\api\summary.py:190`
**后端定义**: `{'GET', 'DELETE'} /api/summary/<summary_id>`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 72. API 未被前端使用

**问题描述**: 后端定义了 /api/summary/<summary_id>/export，但前端未调用

**后端位置**: `server\api\summary.py:212`
**后端定义**: `{'POST'} /api/summary/<summary_id>/export`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 73. API 未被前端使用

**问题描述**: 后端定义了 /api/summary/batch_export，但前端未调用

**后端位置**: `server\api\summary.py:233`
**后端定义**: `{'POST'} /api/summary/batch_export`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 74. API 未被前端使用

**问题描述**: 后端定义了 /api/conversation/mode，但前端未调用

**后端位置**: `server\api\summary.py:271`
**后端定义**: `{'GET'} /api/conversation/mode`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 75. API 未被前端使用

**问题描述**: 后端定义了 /api/conversation/mode，但前端未调用

**后端位置**: `server\api\summary.py:281`
**后端定义**: `{'POST'} /api/conversation/mode`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 76. API 未被前端使用

**问题描述**: 后端定义了 /api/conversation/modes，但前端未调用

**后端位置**: `server\api\summary.py:301`
**后端定义**: `{'GET'} /api/conversation/modes`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 77. API 未被前端使用

**问题描述**: 后端定义了 /api/vision/load，但前端未调用

**后端位置**: `server\api\vision.py:21`
**后端定义**: `{'POST'} /api/vision/load`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 78. API 未被前端使用

**问题描述**: 后端定义了 /api/vision/analyze，但前端未调用

**后端位置**: `server\api\vision.py:32`
**后端定义**: `{'POST'} /api/vision/analyze`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 79. API 未被前端使用

**问题描述**: 后端定义了 /api/vision/ocr，但前端未调用

**后端位置**: `server\api\vision.py:48`
**后端定义**: `{'POST'} /api/vision/ocr`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 80. API 未被前端使用

**问题描述**: 后端定义了 /api/vision/describe，但前端未调用

**后端位置**: `server\api\vision.py:64`
**后端定义**: `{'POST'} /api/vision/describe`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

### 81. API 未被前端使用

**问题描述**: 后端定义了 /api/chat/multimodal，但前端未调用

**后端位置**: `server\api\vision.py:80`
**后端定义**: `{'POST'} /api/chat/multimodal`

**建议**: 确认是否为冗余接口，或前端需要添加调用

---

## 📋 完整的 API 列表

### 前端调用的 API

| 路径 | 方法 | 来源文件 | 行号 |
|------|------|----------|------|
| /api/chat | GET | web\js\api\unified_client.js | 267 |
| /api/copy | GET | web\js\api\api.js | 510 |
| /api/delete | DELETE | web\js\api\api.js | 497 |
| /api/embeddings | GET | web\js\api\api.js | 862 |
| /api/generate | POST | web\js\api\api.js | 199 |
| /api/health | GET | web\js\api\unified_client.js | 25 |
| /api/image/generate | POST | web\image_gallery.html | 229 |
| /api/search | GET | web\js\api\unified_client.js | 267 |
| /api/show | GET | web\js\api\api.js | 404 |
| /api/tags | POST | web\js\api\api.js | 199 |
| /api/tags | GET | web\js\api\api.js | 260 |
| /api/version | GET | web\js\api\api.js | 274 |

### 后端定义的 API

| 路径 | 方法 | 来源文件 | 行号 |
|------|------|----------|------|
| /api/api-key/generate | POST | server\api\api_key.py | 32 |
| /api/api-key/list | GET | server\api\api_key.py | 60 |
| /api/api-key/revoke | POST | server\api\api_key.py | 82 |
| /api/api-key/update | POST | server\api\api_key.py | 112 |
| /api/api-key/verify | POST | server\api\api_key.py | 144 |
| /api/asr/status | GET | server\api\asr.py | 52 |
| /api/asr/transcribe | POST | server\api\asr.py | 69 |
| /api/assistant/computer | POST | server\api\functions.py | 106 |
| /api/assistant/computer/execute | POST | server\api\functions.py | 126 |
| /api/cache/clear | POST | server\api\health.py | 213 |
| /api/cache/stats | GET | server\api\health.py | 147 |
| /api/chat | POST | server\api\chat.py | 262 |
| /api/chat/multimodal | POST | server\api\vision.py | 80 |
| /api/connection/reset | POST | server\api\health.py | 263 |
| /api/connection/status | GET | server\api\health.py | 224 |
| /api/context/clear | OPTIONS, POST | server\api\context.py | 166 |
| /api/context/config | GET, OPTIONS | server\api\context.py | 102 |
| /api/context/config | OPTIONS, POST | server\api\context.py | 114 |
| /api/context/config/reset | OPTIONS, POST | server\api\context.py | 142 |
| /api/context/stats | GET, OPTIONS | server\api\context.py | 177 |
| /api/conversation | POST | server\api\summary.py | 31 |
| /api/conversation/<conversation_id>/context | GET | server\api\summary.py | 105 |
| /api/conversation/<conversation_id>/message | POST | server\api\summary.py | 52 |
| /api/conversation/<conversation_id>/summary | POST | server\api\summary.py | 79 |
| /api/conversation/mode | GET | server\api\summary.py | 271 |
| /api/conversation/mode | POST | server\api\summary.py | 281 |
| /api/conversation/modes | GET | server\api\summary.py | 301 |
| /api/conversations | GET | server\api\summary.py | 121 |
| /api/functions/execute | POST | server\api\functions.py | 46 |
| /api/functions/history | GET | server\api\functions.py | 90 |
| /api/functions/list | GET | server\api\functions.py | 32 |
| /api/group_chat/ask | POST | server\api\group_chat.py | 374 |
| /api/group_chat/auto_chat/pause | POST | server\api\group_chat.py | 202 |
| /api/group_chat/auto_chat/resume | POST | server\api\group_chat.py | 211 |
| /api/group_chat/auto_chat/start | POST | server\api\group_chat.py | 183 |
| /api/group_chat/auto_chat/stop | POST | server\api\group_chat.py | 220 |
| /api/group_chat/characters | GET, POST | server\api\group_chat.py | 150 |
| /api/group_chat/clear | POST | server\api\group_chat.py | 303 |
| /api/group_chat/config | POST | server\api\group_chat.py | 249 |
| /api/group_chat/emotions | GET | server\api\group_chat.py | 235 |
| /api/group_chat/health | GET | server\api\group_chat.py | 131 |
| /api/group_chat/message | POST | server\api\group_chat.py | 350 |
| /api/group_chat/messages | GET | server\api\group_chat.py | 227 |
| /api/group_chat/models | GET | server\api\group_chat.py | 410 |
| /api/group_chat/status | GET | server\api\group_chat.py | 144 |
| /api/group_chat/stream | GET | server\api\group_chat.py | 77 |
| /api/group_chat/summarize | POST | server\api\group_chat.py | 394 |
| /api/group_chat/tts/synthesize | POST | server\api\group_chat.py | 309 |
| /api/group_chat/viewpoints | GET | server\api\group_chat.py | 242 |
| /api/group_chat/world_setting | GET | server\api\group_chat.py | 265 |
| /api/group_chat/world_setting | POST | server\api\group_chat.py | 280 |
| /api/health | GET | server\api\health.py | 26 |
| /api/health/detailed | GET | server\api\health.py | 58 |
| /api/image/generate | POST | server\api\image.py | 214 |
| /api/image/memory | GET | server\api\image.py | 304 |
| /api/image/models | GET | server\api\image.py | 199 |
| /api/image/unload | POST | server\api\image.py | 276 |
| /api/memory | GET | server\api\memory.py | 39 |
| /api/memory | POST | server\api\memory.py | 59 |
| /api/memory/<memory_id> | GET | server\api\memory.py | 92 |
| /api/memory/<memory_id> | PUT | server\api\memory.py | 107 |
| /api/memory/<memory_id> | DELETE | server\api\memory.py | 128 |
| /api/memory/<memory_id>/delete | POST | server\api\memory.py | 129 |
| /api/memory/clear | POST | server\api\memory.py | 177 |
| /api/memory/list | GET | server\api\memory.py | 40 |
| /api/memory/related | GET, POST | server\api\memory.py | 145 |
| /api/memory/search | GET, POST | server\api\memory.py | 144 |
| /api/memory/stats | GET | server\api\memory.py | 190 |
| /api/models | GET | server\api\models.py | 157 |
| /api/models/pull | POST | server\api\models.py | 197 |
| /api/native_llama_cpp_image/health | GET | server\api\health.py | 195 |
| /api/ollama/start | POST | server\api\health.py | 109 |
| /api/ollama/status | GET | server\api\health.py | 85 |
| /api/rag/clear-cache | POST | server\api\rag.py | 98 |
| /api/rag/health | GET | server\api\rag.py | 74 |
| /api/rag/reload | POST | server\api\rag.py | 84 |
| /api/rag/retrieve | POST | server\api\rag.py | 37 |
| /api/rag/stats | GET | server\api\rag.py | 111 |
| /api/rag/status | GET | server\api\rag.py | 64 |
| /api/search/clear-cache | POST | server\api\search.py | 91 |
| /api/search/instant | POST | server\api\search.py | 45 |
| /api/search/news | POST | server\api\search.py | 70 |
| /api/search/web | POST | server\api\search.py | 24 |
| /api/stats | GET | server\api\health.py | 63 |
| /api/summary | GET | server\api\summary.py | 175 |
| /api/summary/<summary_id> | DELETE, GET | server\api\summary.py | 190 |
| /api/summary/<summary_id>/export | POST | server\api\summary.py | 212 |
| /api/summary/batch_export | POST | server\api\summary.py | 233 |
| /api/summary/generate | POST | server\api\summary.py | 148 |
| /api/summary/health | GET | server\api\health.py | 159 |
| /api/vision/analyze | POST | server\api\vision.py | 32 |
| /api/vision/describe | POST | server\api\vision.py | 64 |
| /api/vision/load | POST | server\api\vision.py | 21 |
| /api/vision/ocr | POST | server\api\vision.py | 48 |
| /api/vision/status | GET | server\api\health.py | 177 |
| /api/voice/status | GET | server\api\asr.py | 53 |
| /api/voice/transcribe | POST | server\api\asr.py | 70 |
| /api/whisper/model | GET | server\api\asr.py | 103 |
| /v1/chat/completions | POST | server\api\chat.py | 402 |
| /v1/completions | POST | server\api\chat.py | 403 |
| /v1/models | GET | server\api\models.py | 241 |
