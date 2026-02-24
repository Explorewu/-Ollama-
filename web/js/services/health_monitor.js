/**
 * 服务健康监控 - Health Monitor Service
 * 
 * 功能：
 * - 实时监控所有后端服务状态
 * - 延迟监控和告警
 * - 故障自动检测和恢复通知
 * - 服务状态可视化数据
 * - 性能趋势分析
 */

const HealthMonitor = (function() {
    
    const Config = {
        checkInterval: 15000,
        alertThreshold: {
            responseTime: 5000,
            consecutiveFailures: 3
        },
        historySize: 60,
        autoRecover: true
    };

    let state = {
        isRunning: false,
        checkTimer: null,
        services: {},
        history: {},
        alerts: [],
        listeners: new Set(),
        lastCheckTime: 0
    };

    function init() {
        if (state.isRunning) return;
        
        state.isRunning = true;
        
        initializeServices();
        
        startMonitoring();
        
        console.log('[HealthMonitor] 健康监控已启动');
    }

    function initializeServices() {
        const serviceList = UnifiedAPIClient.getServices();
        
        serviceList.forEach(service => {
            state.services[service.name] = {
                name: service.name,
                baseUrl: service.baseUrl,
                status: 'unknown',
                lastCheck: 0,
                responseTime: 0,
                consecutiveFailures: 0,
                totalChecks: 0,
                successfulChecks: 0,
                uptime: 100,
                lastError: null
            };
            
            state.history[service.name] = [];
        });
    }

    function startMonitoring() {
        if (state.checkTimer) {
            clearInterval(state.checkTimer);
        }
        
        checkAllServices();
        
        state.checkTimer = setInterval(checkAllServices, Config.checkInterval);
    }

    function stopMonitoring() {
        if (state.checkTimer) {
            clearInterval(state.checkTimer);
            state.checkTimer = null;
        }
        state.isRunning = false;
        console.log('[HealthMonitor] 健康监控已停止');
    }

    async function checkAllServices() {
        const healthResults = await UnifiedAPIClient.checkHealth();
        state.lastCheckTime = Date.now();
        
        Object.entries(healthResults).forEach(([serviceName, result]) => {
            updateServiceStatus(serviceName, result);
        });
        
        notifyListeners('healthUpdate', {
            services: getServiceStatus(),
            timestamp: state.lastCheckTime
        });
    }

    function updateServiceStatus(serviceName, result) {
        const service = state.services[serviceName];
        if (!service) return;
        
        const previousStatus = service.status;
        service.lastCheck = Date.now();
        service.totalChecks++;
        
        if (result.status === 'healthy') {
            service.status = 'healthy';
            service.responseTime = result.responseTime;
            service.consecutiveFailures = 0;
            service.successfulChecks++;
            service.lastError = null;
            
            addHistoryEntry(serviceName, {
                status: 'healthy',
                responseTime: result.responseTime,
                timestamp: service.lastCheck
            });
            
            if (previousStatus === 'unhealthy') {
                createAlert(serviceName, 'recovered', `${serviceName} 服务已恢复`);
            }
            
        } else {
            service.status = result.status || 'unhealthy';
            service.responseTime = 0;
            service.consecutiveFailures++;
            service.lastError = result.error || '未知错误';
            
            addHistoryEntry(serviceName, {
                status: 'unhealthy',
                responseTime: 0,
                timestamp: service.lastCheck,
                error: service.lastError
            });
            
            if (service.consecutiveFailures >= Config.alertThreshold.consecutiveFailures) {
                if (previousStatus !== 'unhealthy') {
                    createAlert(serviceName, 'critical', 
                        `${serviceName} 服务不可用: ${service.lastError}`);
                }
            } else if (service.consecutiveFailures >= 1) {
                createAlert(serviceName, 'warning', 
                    `${serviceName} 服务响应异常 (${service.consecutiveFailures}次)`);
            }
        }
        
        service.uptime = service.totalChecks > 0 
            ? Math.round((service.successfulChecks / service.totalChecks) * 100)
            : 100;
    }

    function addHistoryEntry(serviceName, entry) {
        if (!state.history[serviceName]) {
            state.history[serviceName] = [];
        }
        
        state.history[serviceName].push(entry);
        
        if (state.history[serviceName].length > Config.historySize) {
            state.history[serviceName].shift();
        }
    }

    function createAlert(service, level, message) {
        const alert = {
            id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            service,
            level,
            message,
            timestamp: Date.now(),
            acknowledged: false
        };
        
        state.alerts.unshift(alert);
        
        if (state.alerts.length > 50) {
            state.alerts = state.alerts.slice(0, 50);
        }
        
        notifyListeners('alert', alert);
        
        console.warn(`[HealthMonitor] 告警 [${level}] ${service}: ${message}`);
    }

    function acknowledgeAlert(alertId) {
        const alert = state.alerts.find(a => a.id === alertId);
        if (alert) {
            alert.acknowledged = true;
            notifyListeners('alertAcknowledged', alert);
        }
    }

    function clearAlerts() {
        state.alerts = [];
        notifyListeners('alertsCleared', {});
    }

    function getServiceStatus(serviceName = null) {
        if (serviceName) {
            return state.services[serviceName] || null;
        }
        
        return { ...state.services };
    }

    function getServiceHistory(serviceName, limit = 30) {
        const history = state.history[serviceName] || [];
        return history.slice(-limit);
    }

    function getAllHistory() {
        return { ...state.history };
    }

    function getAlerts(unacknowledgedOnly = false) {
        if (unacknowledgedOnly) {
            return state.alerts.filter(a => !a.acknowledged);
        }
        return [...state.alerts];
    }

    function getOverallStatus() {
        const services = Object.values(state.services);
        
        if (services.length === 0) {
            return { status: 'unknown', healthyCount: 0, totalCount: 0 };
        }
        
        const healthyCount = services.filter(s => s.status === 'healthy').length;
        const degradedCount = services.filter(s => s.status === 'degraded').length;
        const unhealthyCount = services.filter(s => s.status === 'unhealthy').length;
        
        let status;
        if (unhealthyCount > 0) {
            status = 'unhealthy';
        } else if (degradedCount > 0) {
            status = 'degraded';
        } else if (healthyCount === services.length) {
            status = 'healthy';
        } else {
            status = 'unknown';
        }
        
        return {
            status,
            healthyCount,
            degradedCount,
            unhealthyCount,
            unknownCount: services.length - healthyCount - degradedCount - unhealthyCount,
            totalCount: services.length,
            avgUptime: Math.round(
                services.reduce((sum, s) => sum + s.uptime, 0) / services.length
            )
        };
    }

    function getPerformanceMetrics(serviceName) {
        const history = state.history[serviceName] || [];
        
        if (history.length === 0) {
            return {
                avgResponseTime: 0,
                minResponseTime: 0,
                maxResponseTime: 0,
                successRate: 0,
                trend: 'unknown'
            };
        }
        
        const responseTimes = history
            .filter(h => h.responseTime > 0)
            .map(h => h.responseTime);
        
        const avgResponseTime = responseTimes.length > 0
            ? Math.round(responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length)
            : 0;
        
        const minResponseTime = responseTimes.length > 0
            ? Math.min(...responseTimes)
            : 0;
        
        const maxResponseTime = responseTimes.length > 0
            ? Math.max(...responseTimes)
            : 0;
        
        const successCount = history.filter(h => h.status === 'healthy').length;
        const successRate = Math.round((successCount / history.length) * 100);
        
        let trend = 'stable';
        if (responseTimes.length >= 5) {
            const recent = responseTimes.slice(-5);
            const older = responseTimes.slice(-10, -5);
            
            if (older.length > 0) {
                const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
                const olderAvg = older.reduce((a, b) => a + b, 0) / older.length;
                
                if (recentAvg > olderAvg * 1.2) {
                    trend = 'degrading';
                } else if (recentAvg < olderAvg * 0.8) {
                    trend = 'improving';
                }
            }
        }
        
        return {
            avgResponseTime,
            minResponseTime,
            maxResponseTime,
            successRate,
            trend,
            dataPoints: history.length
        };
    }

    function addListener(callback) {
        state.listeners.add(callback);
        return () => state.listeners.delete(callback);
    }

    function notifyListeners(event, data) {
        state.listeners.forEach(callback => {
            try {
                callback(event, data);
            } catch (e) {
                console.error('[HealthMonitor] 监听器回调错误:', e);
            }
        });
    }

    function forceCheck() {
        return checkAllServices();
    }

    function updateConfig(newConfig) {
        Object.assign(Config, newConfig);
        
        if (state.isRunning && newConfig.checkInterval) {
            startMonitoring();
        }
    }

    return {
        init,
        start: init,
        stop: stopMonitoring,
        forceCheck,
        
        getServiceStatus,
        getServiceHistory,
        getAllHistory,
        getAlerts,
        getOverallStatus,
        getPerformanceMetrics,
        
        acknowledgeAlert,
        clearAlerts,
        
        addListener,
        updateConfig,
        
        get isRunning() { return state.isRunning; },
        get lastCheckTime() { return state.lastCheckTime; }
    };
})();

if (typeof window !== 'undefined') {
    window.HealthMonitor = HealthMonitor;
    
    document.addEventListener('DOMContentLoaded', () => {
        if (typeof UnifiedAPIClient !== 'undefined') {
            HealthMonitor.init();
        }
    });
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = HealthMonitor;
}
