import json
import psycopg2
conn_string = "dbname= 'odoodb' user='odoo15' password='admin'"
conn = psycopg2.connect(conn_string)
cursor = conn.cursor()
with open("mo.json") as jsonFile:
    manfacturinglist = json.load(jsonFile)
    jsonFile.close()
for manfacturingdata in manfacturinglist:
    # Creating endproduct of manufacturing
    # creating product template data
    product_template = {
        "name": manfacturingdata["poh"]["source_no"],
        "description": manfacturingdata["poh"]["description"],
        "type": "product",
        'categ_id': 1
    }
    cursor.execute('select pp.id from product_template as pt inner join product_product as pp '
                   'on pt.id = pp.product_tmpl_id where company_id = 1 and name = %s ' % ("'" + product_template["name"] + "'"))

    findProduct = cursor.fetchall()
    if len(findProduct) == 0:
        # print("product_template", product_template)
        cursor.execute("""INSERT INTO product_template (name, description,type, categ_id, uom_id, uom_po_id, sale_line_warn,purchase_line_warn, tracking,company_id, sale_ok, purchase_ok, active, service_type, expense_policy, invoice_policy, sale_delay, sequence, purchase_method, produce_delay, service_to_purchase)
                        VALUES(%s, 'Migrated data', %s, %s, 1, 1,'no-message','no-message','none', 1, 'true', 'true', 'true', 'manual', 'no', 'delivery', 0, 1, 'receive', 0, 'false') RETURNING id""", (product_template["name"], product_template["type"], product_template["categ_id"]))

        conn.commit()
        product_template_id = cursor.fetchone()[0]
        print("product_template_id", product_template_id)

        #creating product data
        product_product = {
            "product_tmpl_id": product_template_id,
            "active": 'true',
            "can_image_variant_1024_be_zoomed": False,
            "combination_indices": ""

        }
        product_product_query = 'INSERT INTO product_product (product_tmpl_id, active, can_image_variant_1024_be_zoomed)' \
                                'VALUES (%s,true,false) RETURNING id' %(product_product["product_tmpl_id"])
        cursor.execute(product_product_query)
        conn.commit()
        product_product_id = cursor.fetchone()[0]
        print("product_product_id", product_product_id)
    else:
        product_product_id = findProduct[0][0]


    #Manufacturing production data
    mrp_production = {
        "name": manfacturingdata["order_no"],
        "product_id": product_product_id,
        "product_qty": 1,
        'qty_producing': 1,
        'date_planned_start': manfacturingdata["poh"]["starting_date"],
        'date_finished': manfacturingdata["posting_date"]
    }

    cursor.execute('select * from mrp_production where company_id = 1 and name = %s ' % ("'"+mrp_production["name"]+"'"))
    mrp = cursor.fetchall()

    if len(mrp) == 0 and int(mrp_production['product_qty']) > 0:
        cursor.execute("""INSERT INTO mrp_production (name, product_id, product_qty, qty_producing, date_planned_start, date_finished, picking_type_id, location_src_id, location_dest_id, product_uom_id, company_id, consumption, state, production_location_id)
                        VALUES (%s, %s, %s, %s, %s, %s, 8, 8, 8, 1, 1, 'flexible', 'done', 15) RETURNING id""", (mrp_production["name"], mrp_production["product_id"], mrp_production["product_qty"],mrp_production["qty_producing"], mrp_production["date_planned_start"], mrp_production["date_finished"]))
        conn.commit()
        mrp_production_id = cursor.fetchone()[0]
        print("mrp_production_id", mrp_production_id)

        #Adding BOM
        mrp_bom = {
            "product_tmpl_id": product_template_id,
            "product_qty": 1,
            "create_date": manfacturingdata["posting_date"],
        }
        cursor.execute("""INSERT INTO mrp_bom (product_tmpl_id, product_qty, create_date, active, type, product_uom_id, ready_to_produce, company_id, consumption)
                        VALUES (%s, %s, %s,'true', 'normal', 1, 'asap', 1, 'warning') RETURNING id""", (mrp_bom["product_tmpl_id"], mrp_bom["product_qty"], mrp_bom["create_date"]))
        conn.commit()
        mrp_bom_id = cursor.fetchone()[0]
        print("mrp_bom_id", mrp_bom_id)



        # adding product quantity
        stock_quant = {
            "quantity": manfacturingdata["poh"]["pol"]["quantity"],
            "product_id": product_product_id,
            "in_date": manfacturingdata["posting_date"],
        }
        stock_quant_query = 'INSERT INTO stock_quant (quantity, product_id, location_id, reserved_quantity,company_id)' \
                            'VALUES (%s, %s, 8, 0, 1) RETURNING id' % (
                            stock_quant["quantity"], stock_quant["product_id"])

        cursor.execute(stock_quant_query)
        conn.commit()
        stock_quant_id = cursor.fetchone()[0]
        print("stock_quant_id", stock_quant_id)

        # adding product quantity move for manufactured product
        stock_move = {
            "product_qty": manfacturingdata["poh"]["pol"]["quantity"],
            "product_uom_qty": manfacturingdata["poh"]["pol"]["quantity"],
            "date": manfacturingdata["posting_date"],
            "production_id": mrp_production_id,
            "product_id": product_product_id,
            "name": 'Product Quantity Updated',
        }

        cursor.execute("""INSERT INTO stock_move (product_qty, product_uom_qty, product_id, name, date, production_id, create_date, unit_factor, location_id, company_id, sequence, priority, location_dest_id, procure_method, scrapped, is_done, additional, product_uom, state, picking_type_id, warehouse_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 15, 1, 10, 0, 8, 'make_to_stock', 'false', 'true', 'false', 1, 'done', 8, 1) RETURNING id""",
                       (stock_move["product_qty"], stock_move["product_uom_qty"], stock_move["product_id"],
                        stock_move["name"], stock_move["date"], stock_move["production_id"], stock_move["date"], stock_move["product_qty"]))

        # cursor.execute(stock_move_query)
        conn.commit()
        stock_move_id = cursor.fetchone()[0]
        print("stock_move_id", stock_move_id)

        # adding product quantity move line
        stock_move_line = {
            "move_id": stock_move_id,
            "product_id": product_product_id,
            "qty_done": manfacturingdata["poh"]["pol"]["finished_quantity"],
            "production_id": mrp_production_id,
            "date": manfacturingdata["poh"]["pol"]["starting_date"]
        }

        cursor.execute("""INSERT INTO stock_move_line (move_id, product_id, qty_done, production_id, date ,state, company_id, location_id, location_dest_id, reference,product_uom_id,product_uom_qty)
                        VALUES (%s, %s, %s ,%s ,%s , 'done', 1, 15, 8, 'Migrated data', 1, 1) RETURNING id""",
                       (stock_move_line["move_id"], stock_move_line["product_id"], stock_move_line["qty_done"], stock_move_line["production_id"], stock_move_line["date"]))

        # cursor.execute(stock_move_query)
        conn.commit()
        stock_move_line_id = cursor.fetchone()[0]
        print("stock_move_line_id", stock_move_line_id)

        # Creating Components product for manufacturing
        # creating product template data
        sequence = 0
        for component in manfacturingdata["poh"]["poc"]:
            raw_product_template = {
                "name": component["item_no"],
                "description": component["description"],
                "unit_of_Measure_code": 1 if component["unit_of_Measure_code"] == "STK" else 8,
                "type": "product",
                'categ_id': 1
            }
            cursor.execute('select pp.id from product_template as pt inner join product_product as pp '
                           'on pt.id = pp.product_tmpl_id where company_id = 1 and name = %s ' % (
                                       "'" + raw_product_template["name"] + "'"))

            findRawProduct = cursor.fetchall()
            if len(findRawProduct) == 0:
                # print("product_template", product_template)
                cursor.execute("""INSERT INTO product_template (name, description,type, categ_id, uom_id, uom_po_id, sale_line_warn,purchase_line_warn, tracking,company_id, sale_ok, purchase_ok, active, service_type, expense_policy, invoice_policy, sale_delay,sequence, purchase_method, produce_delay, service_to_purchase)
                                VALUES(%s, 'Migrated data', %s, %s, %s, %s,'no-message','no-message','none', 1, 'true', 'true', 'true', 'manual', 'no', 'delivery', 0, 1, 'receive', 0, 'false') RETURNING id""",
                               (raw_product_template["name"], raw_product_template["type"],
                                raw_product_template["categ_id"], raw_product_template['unit_of_Measure_code'], raw_product_template['unit_of_Measure_code']))

                conn.commit()
                raw_product_template_id = cursor.fetchone()[0]
                print("product_template_id", raw_product_template_id)

                # creating product data
                raw_product_product = {
                    "product_tmpl_id": raw_product_template_id,
                    "active": 'true',
                    "can_image_variant_1024_be_zoomed": False,
                    "combination_indices": ""

                }
                raw_product_product_query = 'INSERT INTO product_product (product_tmpl_id, active, can_image_variant_1024_be_zoomed)' \
                                            'VALUES (%s,true,false) RETURNING id' % (
                                            raw_product_product["product_tmpl_id"])
                cursor.execute(raw_product_product_query)
                conn.commit()
                raw_product_product_id = cursor.fetchone()[0]
                print("product_product_id", raw_product_product_id)
            else:
                raw_product_product_id = findRawProduct[0][0]

            # adding product quantity move for manufactured product
            raw_stock_move = {
                "product_qty": component["act_Consumption_qty"],
                "product_uom_qty": component["act_Consumption_qty"],
                "date": manfacturingdata["posting_date"],
                "unit_of_Measure_code": 1 if component["unit_of_Measure_code"] == "STK" else 8,
                "raw_material_production_id": mrp_production_id,
                "product_id": raw_product_product_id,
                "name": 'Product Quantity Updated'
            }

            cursor.execute("""INSERT INTO stock_move (product_qty, product_uom_qty, product_id, name, date, raw_material_production_id, unit_factor, product_uom, location_id, company_id, sequence, priority, location_dest_id, procure_method, scrapped, is_done, additional, state, picking_type_id, warehouse_id)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 8, 1, 10, 0, 15, 'make_to_stock', 'false', 'true', 'false', 'done', 8, 1) RETURNING id""",
                           (raw_stock_move["product_qty"], raw_stock_move["product_uom_qty"], raw_stock_move["product_id"],
                            raw_stock_move["name"], raw_stock_move["date"], raw_stock_move["raw_material_production_id"], raw_stock_move["product_qty"], raw_stock_move["unit_of_Measure_code"]))

            conn.commit()
            raw_stock_move_id = cursor.fetchone()[0]
            print("stock_move_id", raw_stock_move_id)

            # adding product quantity move line
            raw_stock_move_line = {
                "move_id": raw_stock_move_id,
                "product_id": raw_product_product_id,
                "qty_done": component["act_Consumption_qty"],
                "unit_of_Measure_code": 1 if component["unit_of_Measure_code"] == "STK" else 8,
                "production_id": mrp_production_id,
                "date": manfacturingdata["poh"]["pol"]["starting_date"]
            }

            cursor.execute("""INSERT INTO stock_move_line (move_id, product_id, qty_done, production_id, date , product_uom_id, product_uom_qty ,state, company_id, location_id, location_dest_id, reference)
                                VALUES (%s, %s, %s ,%s ,%s, %s ,%s, 'done', 1, 15, 8, 'Migrated data') RETURNING id""",
                           (raw_stock_move_line["move_id"], raw_stock_move_line["product_id"], raw_stock_move_line["qty_done"],
                            raw_stock_move_line["production_id"], raw_stock_move_line["date"], raw_stock_move_line["unit_of_Measure_code"], raw_stock_move_line["unit_of_Measure_code"]))

            conn.commit()
            raw_stock_move_line_id = cursor.fetchone()[0]
            print("stock_move_line_id", raw_stock_move_line_id)

            # adding bom of line
            sequence = sequence + 1
            mrp_bom_line = {
                "product_id": raw_product_product_id,
                "product_qty": component["expected_quantity"],
                "bom_id": mrp_bom_id,
                "create_date": manfacturingdata["posting_date"],
                "sequence": sequence,
            }

            cursor.execute("""INSERT INTO mrp_bom_line (product_id, product_qty, bom_id, create_date, sequence, company_id, product_uom_id)
                                VALUES (%s, %s, %s, %s, %s, 1, 8 ) RETURNING id""", (mrp_bom_line["product_id"], mrp_bom_line["product_qty"], mrp_bom_line["bom_id"], mrp_bom_line["create_date"], mrp_bom_line["sequence"]))

            conn.commit()
            mrp_bom_line_id = cursor.fetchone()[0]
            print("mrp_bom_line_id", mrp_bom_line_id)



        # Adding workcenter data
        mrp_workcenter = {
            "name": manfacturingdata["work_center_no"],
            "time_efficiency": 100,
            "sequence": 1,
            "active": 'true',
            "working_state": 'normal'

        }

        cursor.execute("""INSERT INTO mrp_workcenter (name, time_efficiency, active, working_state, sequence, resource_id, capacity, costs_hour, time_start, time_stop, oee_target, company_id, resource_calendar_id)
                        VALUES (%s, %s,%s, %s, 1, 1, 1, 0, 0, 0, 90, 1, 1) RETURNING id""", (mrp_workcenter["name"], mrp_workcenter["time_efficiency"], mrp_workcenter["active"], mrp_workcenter["working_state"]))
        conn.commit()
        mrp_workcenter_id = cursor.fetchone()[0]
        print("mrp_workcenter", mrp_workcenter_id)

        for operation in manfacturingdata["operations"]:
            mrp_routing_workcenter = {
                "workcenter_id": mrp_workcenter_id,
                "name": operation["description"],
                "sequence": operation["operation_no"]

            }

            cursor.execute("""INSERT INTO mrp_routing_workcenter (workcenter_id, name, sequence, company_id)
                            VALUES (%s, %s, %s, 1) RETURNING id""", (mrp_routing_workcenter["workcenter_id"], mrp_routing_workcenter["name"], mrp_routing_workcenter["sequence"]))

            conn.commit()
            mrp_routing_workcenter_id = cursor.fetchone()[0]
            print("mrp_routing_workcenter_id", mrp_routing_workcenter_id)


            mrp_routing_workcenter_bom = {
                "workcenter_id": mrp_workcenter_id,
                "name": operation["description"],
                "sequence": operation["operation_no"],
                "bom_id": mrp_bom_id

            }
            cursor.execute("""INSERT INTO mrp_routing_workcenter (workcenter_id, name, sequence, bom_id, company_id, worksheet_type)
                            VALUES (%s, %s, %s, %s, 1, 'text') RETURNING id""", (mrp_routing_workcenter["workcenter_id"], mrp_routing_workcenter["name"], mrp_routing_workcenter["sequence"], mrp_routing_workcenter_bom["bom_id"]))

            conn.commit()
            mrp_routing_workcenter_bom_id = cursor.fetchone()[0]
            print("mrp_routing_workcenter_bom_id", mrp_routing_workcenter_bom_id)



            mrp_workorder = {
                "name": operation["operation_no"],
                "product_id": product_product_id,
                "workcenter_id": mrp_workcenter_id,
                "production_id": mrp_production_id,
                "state": 'done', # operation["status"],
                "operation_id": mrp_routing_workcenter_id,
            }

            print("mrp_workorder", mrp_workorder)

            cursor.execute("""INSERT INTO mrp_workorder (name, product_id, workcenter_id, production_id, state, operation_id, product_uom_id, consumption)
                           VALUES (%s, %s, %s, %s, %s, %s, 1,'flexible') RETURNING id""", (mrp_workorder["name"], mrp_workorder["product_id"], mrp_workorder["workcenter_id"], mrp_workorder["production_id"], mrp_workorder["state"], mrp_workorder["operation_id"]))
            # cursor.execute(mrp_workorder_query)
            conn.commit()
            mrp_workorder_id = cursor.fetchone()[0]
            print("mrp_workcenter", mrp_workorder_id)


        print("Done!")