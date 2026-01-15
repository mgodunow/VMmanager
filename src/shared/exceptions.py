class VMManagementException(Exception):
    """Базовое исключение для системы управления ВМ"""
    pass

class AuthenticationException(VMManagementException):
    """Ошибка аутентификации"""
    pass

class AuthorizationException(VMManagementException):
    """Ошибка авторизации"""
    pass

class VMNotFoundException(VMManagementException):
    """ВМ не найдена"""
    pass

class VMOperationException(VMManagementException):
    """Ошибка операции с ВМ"""
    pass

class DatabaseException(VMManagementException):
    """Ошибка базы данных"""
    pass