from qgis.core import (
    QgsVectorDataProvider,
    QgsFields,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsDataProvider,
    QgsFeatureRequest,
    QgsVectorLayer,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsRectangle,
    QgsSpatialIndex,
    QgsProject,
    QgsProviderRegistry,
    QgsProviderMetadata,
    QgsVectorDataProviderFactory,
    QgsField,
    QgsFeatureStore
)
from qgis.gui import (
    QgsDataSourceWidget,
    QgsSourceSelectProvider,
    QgsDataSourceWidgetFactory,
    QgsDataSourceWidgetManager,
    QgsMapCanvas,
    QgsMapToolIdentifyFeature,
    QgsQueryBuilder,
    QgsMapToolIdentify
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import (
    QWidget, 
    QVBoxLayout, 
    QLabel, 
    QLineEdit, 
    QPushButton, 
    QFileDialog,
    QCheckBox,
    QGroupBox,
    QMessageBox
)
from qgis.PyQt.QtGui import QIcon
import random

# 1. Класс провайдера данных
class CustomVectorDataProvider(QgsVectorDataProvider):
    def __init__(self, uri, options):
        super().__init__(uri, options)
        self.uri = uri
        self._all_features = []
        self._filtered_features = []
        self._fields = QgsFields()
        self._subset_string = ""
        self._spatial_index = None
        self._crs = QgsCoordinateReferenceSystem("EPSG:4326")
        
        # Парсинг параметров из URI
        params = self.parse_uri(uri)
        self.file_path = params.get('file', '')
        self.cache_enabled = params.get('cache', 'false') == 'true'
        self._subset_string = params.get('filter', '')
        
        # Загрузка данных
        self._parse_file(self.file_path)
        self.apply_filter()
        self._build_spatial_index()

    def parse_uri(self, uri):
        """Разбирает URI на параметры"""
        params = {}
        if '?' in uri:
            path_part, query_part = uri.split('?', 1)
            for param in query_part.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key] = value
            params['file'] = path_part.replace('myvec://', '')
        else:
            params['file'] = uri.replace('myvec://', '')
        return params

    def _parse_file(self, file_path):
        """Парсинг пользовательского формата файла"""
        self._fields = QgsFields()
        self._all_features = []
        
        try:
            # Пример структуры файла:
            # HEADER:field1:type1,field2:type2
            # DATA:x1,y1,value1,value2
            
            with open(file_path, 'r') as f:
                # Чтение заголовка
                header_line = f.readline().strip()
                if header_line.startswith('HEADER:'):
                    header = header_line.split(':', 1)[1]
                    for field_def in header.split(','):
                        if ':' in field_def:
                            name, ftype = field_def.split(':', 1)
                            self._fields.append(QgsField(name, self._map_type(ftype)))
                
                # Чтение данных
                for line in f:
                    if line.startswith('DATA:'):
                        parts = line.strip().split(':', 1)[1].split(',')
                        if len(parts) < 2:
                            continue
                            
                        feat = QgsFeature(self._fields)
                        
                        # Парсинг геометрии
                        try:
                            x, y = float(parts[0]), float(parts[1])
                            feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
                        except ValueError:
                            # Если не удалось распарсить координаты
                            continue
                        
                        # Установка атрибутов
                        attrs = []
                        for i in range(2, min(len(parts), len(self._fields) + 2)):
                            value = parts[i]
                            field_type = self._fields[i-2].type()
                            attrs.append(self._convert_value(value, field_type))
                        
                        # Заполняем недостающие атрибуты значениями None
                        while len(attrs) < len(self._fields):
                            attrs.append(None)
                            
                        feat.setAttributes(attrs)
                        self._all_features.append(feat)
        except Exception as e:
            QMessageBox.warning(None, "Ошибка загрузки", f"Не удалось загрузить файл: {str(e)}")
            self._fields = QgsFields()
            self._all_features = []

    def _map_type(self, ftype):
        """Сопоставление типов данных"""
        type_map = {
            'int': QVariant.Int,
            'integer': QVariant.Int,
            'double': QVariant.Double,
            'float': QVariant.Double,
            'string': QVariant.String,
            'text': QVariant.String,
            'date': QVariant.Date,
            'datetime': QVariant.DateTime,
            'bool': QVariant.Bool
        }
        return type_map.get(ftype.lower(), QVariant.String)

    def _convert_value(self, value, vtype):
        """Конвертация строковых значений в нужный тип"""
        if value == "":
            return None
            
        try:
            if vtype == QVariant.Int:
                return int(value)
            elif vtype == QVariant.Double:
                return float(value)
            elif vtype == QVariant.Date:
                return QDate.fromString(value, Qt.ISODate)
            elif vtype == QVariant.DateTime:
                return QDateTime.fromString(value, Qt.ISODate)
            elif vtype == QVariant.Bool:
                return value.lower() in ['true', '1', 'yes']
            return value
        except:
            return value

    def apply_filter(self):
        """Применяет атрибутивный фильтр к данным"""
        if not self._subset_string:
            self._filtered_features = self._all_features[:]
            return
        
        try:
            expression = QgsExpression(self._subset_string)
            if expression.hasParserError():
                print(f"Ошибка парсера: {expression.parserErrorString()}")
                self._filtered_features = self._all_features[:]
                return
            
            context = QgsExpressionContext()
            context.appendScope(QgsExpressionContextUtils.globalScope())
            context.appendScope(QgsExpressionContextUtils.projectScope(QgsProject.instance()))
            
            self._filtered_features = []
            for feature in self._all_features:
                context.setFeature(feature)
                if expression.evaluate(context):
                    self._filtered_features.append(feature)
        except Exception as e:
            print(f"Ошибка применения фильтра: {str(e)}")
            self._filtered_features = self._all_features[:]

    def _build_spatial_index(self):
        """Строит пространственный индекс для быстрого поиска"""
        self._spatial_index = QgsSpatialIndex()
        for feature in self._filtered_features:
            if feature.hasGeometry():
                self._spatial_index.addFeature(feature)

    # Реализация обязательных методов провайдера
    def wkbType(self):
        return QgsWkbTypes.Point

    def crs(self):
        return self._crs

    def featureCount(self):
        return len(self._filtered_features)

    def fields(self):
        return self._fields

    def getFeatures(self, request=QgsFeatureRequest()):
        """Возвращает итератор объектов с учетом всех фильтров"""
        # Пространственный фильтр
        if request.filterRect() and request.filterRect().isFinite():
            rect = request.filterRect()
            candidate_ids = self._spatial_index.intersects(rect)
            
            for fid in candidate_ids:
                feature = next((f for f in self._filtered_features if f.id() == fid), None)
                if feature and feature.hasGeometry():
                    # Точная проверка пересечения
                    engine = QgsGeometry.createGeometryEngine(feature.geometry().constGet())
                    engine.prepareGeometry()
                    if engine.intersects(rect.constGet()):
                        yield feature
        else:
            # Возвращаем все объекты
            for feature in self._filtered_features:
                yield feature

    def identify(self, point, tolerance, layer_units_per_pixel, context):
        """
        Идентификация объектов в заданной точке
        :param point: QgsPointXY - точка для идентификации
        :param tolerance: float - допуск в пикселях
        :param layer_units_per_pixel: float - преобразование пикселей в единицы слоя
        :param context: QgsIdentifyContext - контекст идентификации
        :return: список результатов идентификации
        """
        from qgis.gui import QgsMapToolIdentify
        results = []
        search_radius = tolerance * layer_units_per_pixel
        
        # Создаем область поиска (круг)
        search_area = QgsGeometry.fromPointXY(point).buffer(search_radius, 5)
        
        # Используем пространственный индекс для поиска кандидатов
        candidate_ids = self._spatial_index.intersects(search_area.boundingBox())
        
        # Проверяем точное попадание
        for fid in candidate_ids:
            feature = next((f for f in self._filtered_features if f.id() == fid), None)
            if feature and feature.hasGeometry():
                # Проверяем попадание в геометрию
                if feature.geometry().intersects(search_area):
                    result = QgsMapToolIdentify.IdentifyResult()
                    result.mLayer = self.vectorLayer()
                    result.mFeature = feature
                    results.append(result)
        
        return results

    def setSubsetString(self, subset):
        """Устанавливает атрибутивный фильтр"""
        self._subset_string = subset
        self.apply_filter()
        self._build_spatial_index()
        self.dataChanged.emit()
        return True

    def subsetString(self):
        return self._subset_string

    def capabilities(self):
        return (QgsVectorDataProvider.SelectAtId | 
                QgsVectorDataProvider.ReadLayerInfo |
                QgsVectorDataProvider.SelectAtId |
                QgsVectorDataProvider.CreateSpatialIndex |
                QgsVectorDataProvider.FastTruncate |
                QgsVectorDataProvider.SelectEncoding |
                QgsVectorDataProvider.CreateAttributeIndex |
                QgsVectorDataProvider.DeleteFeatures |
                QgsVectorDataProvider.ChangeAttributeValues)

    def extent(self):
        """Возвращает экстент слоя"""
        bbox = QgsRectangle()
        for feature in self._filtered_features:
            if feature.hasGeometry():
                bbox.combineExtentWith(feature.geometry().boundingBox())
        return bbox

    def uniqueValues(self, fieldIndex, limit=-1):
        """Возвращает уникальные значения поля"""
        values = set()
        for feature in self._all_features:
            values.add(feature.attribute(fieldIndex))
        return list(values)[:limit] if limit > 0 else list(values)

# 2. Фабрика провайдера
class CustomVectorProviderFactory(QgsVectorDataProviderFactory):
    def createProvider(self, uri, options):
        return CustomVectorDataProvider(uri, options)
    
    def supportsUri(self, uri):
        return uri.startswith('myvec://') or uri.endswith('.myvec')
    
    def createDataSource(self, uri, options):
        return uri

# 3. Метаданные провайдера
class CustomVectorProviderMetadata(QgsProviderMetadata):
    def __init__(self):
        super().__init__(
            'my_custom_provider',
            'Custom Vector Provider',
            CustomVectorProviderFactory()
        )

# 4. Виджеты для интерфейса
class CustomOptionsWidget(QWidget):
    """Виджет с дополнительными опциями"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.current_filter = ""
        
        # Поле для пути к файлу
        self.layout().addWidget(QLabel("Файл:"))
        self.file_edit = QLineEdit()
        self.layout().addWidget(self.file_edit)
        
        # Кнопка обзора
        self.browse_btn = QPushButton("Обзор...")
        self.browse_btn.clicked.connect(self.browse_file)
        self.layout().addWidget(self.browse_btn)
        
        # Кнопка фильтра
        self.filter_btn = QPushButton("Установить фильтр...")
        self.filter_btn.clicked.connect(self.set_filter)
        self.layout().addWidget(self.filter_btn)
        
        # Поле текущего фильтра
        self.filter_label = QLabel("Фильтр: не задан")
        self.layout().addWidget(self.filter_label)
        
        # Другие настройки
        self.cache_checkbox = QCheckBox("Кэшировать данные")
        self.layout().addWidget(self.cache_checkbox)
        
        self.layout().addStretch()

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл", "", "Custom Vector Files (*.myvec)"
        )
        if file_path:
            self.file_edit.setText(file_path)

    def set_filter(self):
        """Открывает диалог для установки фильтра"""
        if not self.file_edit.text():
            return
            
        # Создаем временный слой для диалога фильтрации
        layer = QgsVectorLayer(f"myvec://?file={self.file_edit.text()}", "temp", "memory")
        if not layer.isValid():
            return
            
        dialog = QgsQueryBuilder(layer)
        dialog.setSubsetString(self.current_filter)
        
        if dialog.exec_():
            self.current_filter = dialog.subsetString()
            self.filter_label.setText(f"Фильтр: {self.current_filter if self.current_filter else 'не задан'}")

    def get_uri(self):
        """Формирует URI из текущих настроек"""
        file_path = self.file_edit.text()
        if not file_path:
            return ""
            
        uri = f"myvec://?file={file_path}"
        
        if self.cache_checkbox.isChecked():
            uri += "&cache=true"
            
        if self.current_filter:
            uri += f"&filter={self.current_filter}"
            
        return uri

class CustomPreviewWidget(QWidget):
    """Виджет предварительного просмотра данных"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        
        # Карта для предпросмотра
        self.canvas = QgsMapCanvas()
        self.canvas.setMinimumSize(400, 300)
        self.layout().addWidget(self.canvas)
        
        # Инструмент идентификации
        self.identify_tool = QgsMapToolIdentifyFeature(self.canvas)
        self.identify_tool.featureIdentified.connect(self.on_feature_identified)
        
        # Информация об объекте
        self.info_label = QLabel("Выберите объект на карте")
        self.layout().addWidget(self.info_label)
        
        self.current_layer = None

    def load_layer(self, uri):
        """Загружает слой для предпросмотра"""
        if self.current_layer:
            QgsProject.instance().removeMapLayer(self.current_layer)
        
        self.current_layer = QgsVectorLayer(uri, "Preview Layer", "my_custom_provider")
        if self.current_layer.isValid():
            QgsProject.instance().addMapLayer(self.current_layer, False)
            self.canvas.setLayers([self.current_layer])
            self.canvas.setExtent(self.current_layer.extent())
            self.canvas.refresh()
            self.canvas.setMapTool(self.identify_tool)
            self.identify_tool.setLayer(self.current_layer)
        else:
            self.info_label.setText("Ошибка загрузки слоя для предпросмотра")

    def on_feature_identified(self, feature):
        """Обработка выбора объекта"""
        attrs = feature.attributes()
        info = " | ".join([str(a) for a in attrs])
        self.info_label.setText(f"Объект ID={feature.id()}: {info}")

class CustomVectorSourceWidget(QgsDataSourceWidget):
    """Виджет для отображения в стандартной векторной вкладке"""
    def __init__(self, parent=None, fl=None):
        super().__init__(parent, fl)
        self.setLayout(QVBoxLayout())
        
        # Группа для наших опций
        self.opt_group = QGroupBox("Опции формата MYVEC")
        self.opt_group.setLayout(QVBoxLayout())
        self.layout().addWidget(self.opt_group)
        
        # Виджет с нашими специфическими настройками
        self.options_widget = CustomOptionsWidget()
        self.opt_group.layout().addWidget(self.options_widget)
        
        # Виджет предварительного просмотра
        self.preview_widget = CustomPreviewWidget()
        self.layout().addWidget(self.preview_widget)
        
        # Кнопка для загрузки данных
        self.add_btn = QPushButton("Добавить слой")
        self.add_btn.clicked.connect(self.add_layer)
        self.layout().addWidget(self.add_btn)

    def setDataSourceUri(self, uri):
        """Устанавливает текущий URI"""
        self.options_widget.file_edit.setText(uri.replace('myvec://?file=', ''))
        self.preview_widget.load_layer(uri)

    def dataSourceUri(self):
        """Возвращает текущий URI с параметрами"""
        return self.options_widget.get_uri()

    def add_layer(self):
        """Добавляет слой с текущими настройками"""
        uri = self.dataSourceUri()
        layer = QgsVectorLayer(uri, "Custom Layer", "my_custom_provider")
        
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось загрузить слой")

# 5. Фабрика виджетов
class CustomVectorWidgetFactory(QgsDataSourceWidgetFactory):
    """Фабрика для создания виджета настроек нашего формата"""
    def __init__(self):
        super().__init__()
        self.setTitle("MYVEC Format Options")

    def createWidget(self, parent, widgetMode):
        return CustomVectorSourceWidget(parent, widgetMode)

    def supportsUri(self, uri):
        """Активируем виджет только для наших файлов"""
        return uri.lower().endswith('.myvec') or uri.startswith('myvec://')

# 6. Провайдер вкладки
class CustomSourceSelectProvider(QgsSourceSelectProvider):
    def providerKey(self):
        return 'my_custom_provider'
    
    def text(self):
        return "Мой формат"
    
    def createDataSourceWidget(self, parent=None, fl=None):
        return CustomVectorSourceWidget(parent, fl)

# 7. Инструмент идентификации
class CustomIdentifyTool(QgsMapToolIdentify):
    """Кастомный инструмент идентификации для нашего формата"""
    def __init__(self, canvas):
        super().__init__(canvas)
    
    def identify(self, x, y, layerList, mode, tolerance=5):
        """Переопределяем метод идентификации"""
        results = []
        point = self.toMapCoordinates(x, y)
        layer_units_per_pixel = self.canvas().mapUnitsPerPixel()
        
        for layer in layerList:
            if isinstance(layer, QgsVectorLayer) and layer.dataProvider().name() == 'my_custom_provider':
                # Используем нашу реализацию идентификации
                results.extend(layer.dataProvider().identify(
                    point,
                    tolerance,
                    layer_units_per_pixel,
                    self.context()
                ))
            else:
                # Стандартная идентификация для других слоев
                results.extend(super().identify(x, y, layerList, mode, tolerance))
        
        return results

# 8. Инициализация плагина
def initProvider():
    # Регистрация провайдера данных
    registry = QgsProviderRegistry.instance()
    registry.registerProvider(CustomVectorProviderMetadata())
    
    # Регистрация фабрики виджетов
    widget_factory = CustomVectorWidgetFactory()
    QgsGui.dataSourceWidgetManager().registerWidgetFactory(widget_factory)
    
    # Регистрация отдельной вкладки
    iface.registerDataSourceWidgetProvider(CustomSourceSelectProvider())
    
    # Регистрация инструмента идентификации
    iface.registerMapTool(CustomIdentifyTool(iface.mapCanvas()))
    
    # Установка инструмента по умолчанию
    iface.mapCanvas().setMapTool(CustomIdentifyTool(iface.mapCanvas()))

def initGui():
    initProvider()

def unload():
    # Удаление регистраций при выгрузке плагина
    registry = QgsProviderRegistry.instance()
    registry.unregisterProvider('my_custom_provider')
    
    widget_manager = QgsGui.dataSourceWidgetManager()
    widget_manager.unregisterWidgetFactory('MYVEC Format Options')
    
    iface.unregisterDataSourceWidgetProvider('my_custom_provider')
    iface.unregisterMapTool(CustomIdentifyTool)
