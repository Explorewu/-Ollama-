/**
 * 模块管理器
 * 统一管理所有功能模块的加载和初始化
 */
const ModuleManager = (function() {
    const modules = {};
    
    return {
        register: function(name, module) {
            modules[name] = module;
            console.log('[ModuleManager] 模块 ' + name + ' 已注册');
        },
        
        get: function(name) {
            return modules[name] || null;
        },
        
        initAll: function(app) {
            Object.keys(modules).forEach(function(name) {
                var module = modules[name];
                if (typeof module.init === 'function') {
                    try {
                        module.init(app);
                        console.log('[ModuleManager] 模块 ' + name + ' 初始化成功');
                    } catch (error) {
                        console.error('[ModuleManager] 模块 ' + name + ' 初始化失败:', error);
                    }
                }
            });
        },
        
        call: function(moduleName, methodName, args, fallback) {
            args = args || [];
            var module = this.get(moduleName);
            if (module && typeof module[methodName] === 'function') {
                return module[methodName].apply(module, args);
            } else if (fallback) {
                console.warn('[ModuleManager] 模块 ' + moduleName + ' 不存在或方法 ' + methodName + ' 未找到，使用降级实现');
                return fallback.apply(null, args);
            } else {
                console.error('[ModuleManager] 模块 ' + moduleName + '.' + methodName + ' 不存在且无降级实现');
                return null;
            }
        }
    };
})();

// 自动注册已加载的模块
(function() {
    var registeredModules = ['AppEvents', 'AppSearch', 'AppGroup'];
    registeredModules.forEach(function(name) {
        if (typeof window[name] !== 'undefined') {
            var moduleName = name.replace('App', '').toLowerCase();
            ModuleManager.register(moduleName, window[name]);
        }
    });
    
    if (typeof window.UnifiedAPIClient !== 'undefined') {
        ModuleManager.register('unifiedApiClient', window.UnifiedAPIClient);
    }
    
    if (typeof window.HealthMonitor !== 'undefined') {
        ModuleManager.register('healthMonitor', window.HealthMonitor);
    }
})();

// 导出模块
if (typeof window !== 'undefined') {
    window.ModuleManager = ModuleManager;
}
