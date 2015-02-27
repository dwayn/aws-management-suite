from amslib.core.manager import BaseManager



class ArgumentCompletion(BaseManager):

    def _general_db_completion(self, table, column, need_distinct=True):
        rval = []
        distinct = ''
        if need_distinct:
            distinct = 'distinct'
        self.db.execute("select {0} {1} from {2}".format(distinct, column, table))
        rows = self.db.fetchall()
        if rows:
            for row in rows:
                if row[0]:
                    rval.append(row[0])
        return rval



    def security_group_id(self, **kwargs):
        return self._general_db_completion('security_groups', 'security_group_id', False)


    def security_group_vpc(self, **kwargs):
        return self._general_db_completion('security_groups', 'vpc_id', True)


    def security_group_name(self, **kwargs):
        return self._general_db_completion('security_groups', 'name', False)


    def region(self, **kwargs):
        return self._general_db_completion('availability_zones', 'region', True)

    def availability_zone(self, **kwargs):
        return self._general_db_completion('availability_zones', 'availability_zone', False)




