import re


"""
task specification for JEDI

"""
class JediTaskSpec(object):
    # attributes
    attributes = (
        'jediTaskID','taskName','status','userName',
        'creationDate','modificationTime','startTime','endTime',
        'frozenTime','prodSourceLabel','workingGroup','vo','coreCount',
        'taskType','processingType','taskPriority','currentPriority',
        'architecture','transUses','transHome','transPath','lockedBy',
        'lockedTime','termCondition','splitRule','walltime','walltimeUnit',
        'outDiskCount','outDiskUnit','workDiskCount','workDiskUnit',
        'ramCount','ramUnit','ioIntensity','ioIntensityUnit',
        'workQueue_ID','progress','failureRate','errorDialog',
        'reqID','oldStatus','cloud','site'
        )
    # attributes which have 0 by default
    _zeroAttrs = ()
    # attributes to force update
    _forceUpdateAttrs = ('lockedBy','lockedTime')
    # mapping between sequence and attr
    _seqAttrMap = {}
    # limit length
    _limitLength = {'errorDialog' : 255}



    # constructor
    def __init__(self):
        # install attributes
        for attr in self.attributes:
            if attr in self._zeroAttrs:
                object.__setattr__(self,attr,0)
            else:
                object.__setattr__(self,attr,None)
        # map of changed attributes
        object.__setattr__(self,'_changedAttrs',{})
        # template to generate job parameters
        object.__setattr__(self,'jobParamsTemplate','')
        # associated datasets
        object.__setattr__(self,'datasetSpecList',[])


    # override __setattr__ to collecte the changed attributes
    def __setattr__(self,name,value):
        oldVal = getattr(self,name)
        object.__setattr__(self,name,value)
        newVal = getattr(self,name)
        # collect changed attributes
        if oldVal != newVal or name in self._forceUpdateAttrs:
            self._changedAttrs[name] = value


    # reset changed attribute list
    def resetChangedList(self):
        object.__setattr__(self,'_changedAttrs',{})


    # reset changed attribute
    def resetChangedAttr(self,name):
        try:
            del self._changedAttrs[name]
        except:
            pass


    # force update
    def forceUpdate(self,name):
        if name in self.attributes:
            self._changedAttrs[name] = getattr(self,name)
        
    
    # return map of values
    def valuesMap(self,useSeq=False,onlyChanged=False):
        ret = {}
        for attr in self.attributes:
            # use sequence
            if useSeq and self._seqAttrMap.has_key(attr):
                continue
            # only changed attributes
            if onlyChanged:
                if not self._changedAttrs.has_key(attr):
                    continue
            val = getattr(self,attr)
            if val == None:
                if attr in self._zeroAttrs:
                    val = 0
                else:
                    val = None
            # truncate too long values
            if self._limitLength.has_key(attr):
                if val != None:
                    val = val[:self._limitLength[attr]]
            ret[':%s' % attr] = val
        return ret


    # pack tuple into TaskSpec
    def pack(self,values):
        for i in range(len(self.attributes)):
            attr= self.attributes[i]
            val = values[i]
            object.__setattr__(self,attr,val)


    # return column names for INSERT
    def columnNames(cls,prefix=None):
        ret = ""
        for attr in cls.attributes:
            if prefix != None:
                ret += '{0}.'.format(prefix)
            ret += '{0},'.format(attr)
        ret = ret[:-1]
        return ret
    columnNames = classmethod(columnNames)


    # return expression of bind variables for INSERT
    def bindValuesExpression(cls,useSeq=True):
        ret = "VALUES("
        for attr in cls.attributes:
            if useSeq and cls._seqAttrMap.has_key(attr):
                ret += "%s," % cls._seqAttrMap[attr]
            else:
                ret += ":%s," % attr
        ret = ret[:-1]
        ret += ")"            
        return ret
    bindValuesExpression = classmethod(bindValuesExpression)

    
    # return an expression of bind variables for UPDATE to update only changed attributes
    def bindUpdateChangesExpression(self):
        ret = ""
        for attr in self.attributes:
            if self._changedAttrs.has_key(attr):
                ret += '%s=:%s,' % (attr,attr)
        ret  = ret[:-1]
        ret += ' '
        return ret



    # get the max size per job if defined
    def getMaxSizePerJob(self):
        if self.splitRule != None:
            tmpMatch = re.search('NGBPJ=(\d+)',self.splitRule)
            if tmpMatch != None:
                nGBPerJob = int(nGBPerJob) * 1024 * 1024 * 1024
                return nGBPerJob
        return None    



    # get the maxnumber of files per job if defined
    def getMaxNumFilesPerJob(self):
        if self.splitRule != None:
            tmpMatch = re.search('NMFPJ=(\d+)',self.splitRule)
            if tmpMatch != None:
                return int(tmpMatch.group(1))
        return None    




    # get the number of files per job if defined
    def getNumFilesPerJob(self):
        if self.splitRule != None:
            tmpMatch = re.search('NFPJ=(\d+)',self.splitRule)
            if tmpMatch != None:
                return int(tmpMatch.group(1))
        return None    
        


    # get the number of events per job if defined
    def getNumEventsPerJob(self):
        if self.splitRule != None:
            tmpMatch = re.search('NEPJ=(\d+)',self.splitRule)
            if tmpMatch != None:
                return int(tmpMatch.group(1))
        return None    
        


    # get offset for random seed
    def getRndmSeedOffset(self):
        if self.splitRule != None:
            tmpMatch = re.search('RNDM=(\d+)',self.splitRule)
            if tmpMatch != None:
                return int(tmpMatch.group(1))
        return 0



    # get offset for first event
    def getFirstEventOffset(self):
        if self.splitRule != None:
            tmpMatch = re.search('FST=(\d+)',self.splitRule)
            if tmpMatch != None:
                return int(tmpMatch.group(1))
        return 0


    
    # get the size of workDisk in bytes
    def getWorkDiskSize(self):
        tmpSize = self.workDiskCount
        if tmpSize == None:
            return 0
        if self.workDiskUnit == 'GB':
            tmpSize = tmpSize * 1024 * 1024 * 1024
            return tmpSize
        if self.workDiskUnit == 'MB':
            tmpSize = tmpSize * 1024 * 1024
            return tmpSize
        return tmpSize



    # get the size of outDisk in bytes
    def getOutDiskSize(self):
        tmpSize = self.outDiskCount
        if tmpSize == None:
            return 0
        if self.outDiskUnit == 'GB':
            tmpSize = tmpSize * 1024 * 1024 * 1024
            return tmpSize
        if self.outDiskUnit == 'MB':
            tmpSize = tmpSize * 1024 * 1024
            return tmpSize
        return tmpSize



    # return list of status to update contents
    def statusToUpdateContents(cls):
        return ['defined','pending']
    statusToUpdateContents = classmethod(statusToUpdateContents)


    # set task status on hold
    def setOnHold(self):
        # change status
        if self.status in ['ready','running','merging','scouting']:
            self.oldStatus = self.status
            self.status = 'pending'


    # return list of status to reject external changes
    def statusToRejectExtChange(cls):
        return ['finised','prepared','broken','aborted','aborting','finishing']
    statusToRejectExtChange = classmethod(statusToRejectExtChange)


    # return mapping of terminate command and status
    def terminateCommandStatusMap(cls):
        return {'kill' : {'doing': 'aborting',
                          'done' : 'aborted'},
                'finish' : {'doing': 'finishing',
                            'done' : 'prepared'}
                }
    terminateCommandStatusMap = classmethod(terminateCommandStatusMap)



    # set task status to active
    def setInActive(self):
        # change status
        if self.status == 'pending':
            self.status = self.oldStatus
            self.oldStatus = None
        # reset error dialog    
        self.setErrDiag(None)
            
            
    # set error dialog
    def setErrDiag(self,diag):
        # set error dialog    
        self.errorDialog = diag
        

        
