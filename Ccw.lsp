(defun c:CheckPolygonOrientation ( / ent obj coords n area i x1 y1 x2 y2)
    (vl-load-com) ; Загрузка расширений ActiveX
    
    (setq ent (car (entsel "\nВыберите замкнутую полилинию: ")))
    (if ent
        (progn
            (setq obj (vlax-ename->vla-object ent))
            (if (and
                    (eq (vla-get-objectname obj) "AcDbPolyline") ; Проверка типа объекта
                    (eq (vla-get-closed obj) :vlax-true)         ; Проверка замкнутости
                (progn
                    (setq coords (vlax-get obj 'coordinates))    ; Получение координат
                    (setq n (/ (length coords) 2))               ; Количество точек
                    (setq area 0.0)
                    
                    ; Вычисление площади по формуле Гаусса
                    (setq i 0)
                    (repeat n
                        ; Текущая вершина
                        (setq x1 (nth (* i 2) coords))
                        (setq y1 (nth (1+ (* i 2)) coords))
                        
                        ; Следующая вершина (с замыканием на первую)
                        (if (= i (1- n))
                            (setq j 0)
                            (setq j (1+ i))
                        )
                        (setq x2 (nth (* j 2) coords))
                        (setq y2 (nth (1+ (* j 2)) coords))
                        
                        ; Суммирование
                        (setq area (+ area (- (* x1 y2) (* x2 y1))))
                        (setq i (1+ i))
                    )
                    
                    ; Определение ориентации
                    (if (> area 0.0)
                        (alert "Ориентация: против часовой стрелки (CCW)")
                        (alert "Ориентация: по часовой стрелке (CW)")
                    )
                )
                (alert "Объект не является замкнутой полилинией!")
            )
        )
        (alert "Объект не выбран!")
    )
    (princ)
)
