import sys
import time
import datetime

from pandajedi.jedicore.ThreadUtils import ListWithLock,ThreadPool,WorkerThread
from pandajedi.jedicore import Interaction
from pandajedi.jedicore.MsgWrapper import MsgWrapper
from pandajedi.jedicore.FactoryBase import FactoryBase
from JediKnight import JediKnight

from pandajedi.jediconfig import jedi_config


# logger
from pandacommon.pandalogger.PandaLogger import PandaLogger
logger = PandaLogger().getLogger(__name__.split('.')[-1])


# worker class to refine TASK_PARAM to fill JEDI tables 
class TaskBroker (JediKnight,FactoryBase):

    # constructor
    def __init__(self,commuChannel,taskBufferIF,ddmIF,vos,prodSourceLabels):
        self.vos = self.parseInit(vos)
        self.prodSourceLabels = self.parseInit(prodSourceLabels)
        JediKnight.__init__(self,commuChannel,taskBufferIF,ddmIF,logger)
        FactoryBase.__init__(self,self.vos,self.prodSourceLabels,logger,
                             jedi_config.taskbroker.modConfig)


    # main
    def start(self):
        # start base classes
        JediKnight.start(self)
        FactoryBase.initializeMods(self,self.taskBufferIF,self.ddmIF)
        # go into main loop
        while True:
            startTime = datetime.datetime.utcnow()
            try:
                # get logger
                tmpLog = MsgWrapper(logger)
                tmpLog.debug('start')
                # get work queue mapper
                workQueueMapper = self.taskBufferIF.getWrokQueueMap()
                # loop over all vos
                for vo in self.vos:
                    # loop over all sourceLabels
                    for prodSourceLabel in self.prodSourceLabels:
                        # loop over all work queues
                        for workQueue in workQueueMapper.getQueueListWithVoType(vo,prodSourceLabel):
                            tmpLog.debug('vo={0} label={1} queue={2}'.format(vo,prodSourceLabel,workQueue.queue_name))
                            # get the list of tasks to check
                            tmpList = self.taskBufferIF.getTasksToCheckAssignment_JEDI(vo,prodSourceLabel,workQueue)
                            if tmpList == None:
                                # failed
                                tmpLog.error('failed to get the list of tasks to check')
                            else:
                                tmpLog.debug('got {0} tasks to check'.format(len(tmpList)))
                                # put to a locked list
                                taskList = ListWithLock(tmpList)
                                # make thread pool
                                threadPool = ThreadPool()
                                # make workers
                                nWorker = jedi_config.taskbroker.nWorkers
                                for iWorker in range(nWorker):
                                    thr = TaskCheckerThread(taskList,threadPool,
                                                            self.taskBufferIF,
                                                            self.ddmIF,self,
                                                            vo,prodSourceLabel)
                                    thr.start()
                                # join
                                threadPool.join()
                            # get the list of tasks to assign
                            tmpList = self.taskBufferIF.getTasksToAssign_JEDI(vo,prodSourceLabel,workQueue)
                            if tmpList == None:
                                # failed
                                tmpLog.error('failed to get the list of tasks to assign')
                            else:
                                tmpLog.debug('got {0} tasks to assign'.format(len(tmpList)))
                                # put to a locked list
                                taskList = ListWithLock(tmpList)
                                # make thread pool
                                threadPool = ThreadPool()
                                # make workers
                                nWorker = jedi_config.taskbroker.nWorkers
                                for iWorker in range(nWorker):
                                    thr = TaskBrokerThread(taskList,threadPool,
                                                           self.taskBufferIF,
                                                           self.ddmIF,self,
                                                           vo,prodSourceLabel,
                                                           workQueue)
                                    thr.start()
                                # join
                                threadPool.join()
            except:
                errtype,errvalue = sys.exc_info()[:2]
                tmpLog.error('failed in {0}.start() with {1} {2}'.format(self.__class__.__name__,
                                                                         errtype.__name__,errvalue))
            tmpLog.debug('done')                                
            # sleep if needed
            loopCycle = jedi_config.taskbroker.loopCycle
            timeDelta = datetime.datetime.utcnow() - startTime
            sleepPeriod = loopCycle - timeDelta.seconds
            if sleepPeriod > 0:
                time.sleep(sleepPeriod)



# thread for real worker
class TaskCheckerThread (WorkerThread):

    # constructor
    def __init__(self,taskList,threadPool,taskbufferIF,ddmIF,implFactory,
                 vo,prodSourceLabel):
        # initialize woker with no semaphore
        WorkerThread.__init__(self,None,threadPool,logger)
        # attributres
        self.taskList = taskList
        self.taskBufferIF = taskbufferIF
        self.ddmIF = ddmIF.getInterface(vo)
        self.implFactory = implFactory
        self.vo = vo
        self.prodSourceLabel = prodSourceLabel


    # main
    def runImpl(self):
        while True:
            try:
                # get a part of list
                nTasks = 100
                taskList = self.taskList.get(nTasks)
                # no more datasets
                if len(taskList) == 0:
                    self.logger.debug('{0} terminating since no more items'.format(self.__class__.__name__))
                    return
                # make logger
                tmpLog = MsgWrapper(self.logger)
                tmpLog.info('start')
                tmpStat = Interaction.SC_SUCCEEDED
                # get TaskSpecs
                taskSpecList = []
                for jediTaskID in taskList:
                    tmpRet,taskSpec = self.taskBufferIF.getTaskWithID_JEDI(jediTaskID,False)
                    if tmpRet and taskSpec != None:
                        taskSpecList.append(taskSpec)
                    else:
                        tmpLog.error('failed to get taskSpec for jediTaskID={0}'.format(jediTaskID))
                if taskSpecList != []:
                    # get impl                    
                    if tmpStat == Interaction.SC_SUCCEEDED:                    
                        tmpLog.info('getting Impl')
                        try:
                            impl = self.implFactory.getImpl(self.vo,self.prodSourceLabel)
                            if impl == None:
                                # task brokerage is undefined
                                tmpLog.error('task broker is undefined for vo={0} sourceLabel={1}'.format(self.vo,self.prodSourceLabel))
                                tmpStat = Interaction.SC_FAILED
                        except:
                            errtype,errvalue = sys.exc_info()[:2]
                            tmpLog.error('getImpl failed with {0}:{1}'.format(errtype.__name__,errvalue))
                            tmpStat = Interaction.SC_FAILED
                    # check
                    if tmpStat == Interaction.SC_SUCCEEDED:
                        tmpLog.info('brokerage with {0}'.format(impl.__class__.__name__))
                        try:
                            tmpStat,taskCloudMap = impl.doCheck(taskSpecList)
                        except:
                            errtype,errvalue = sys.exc_info()[:2]
                            tmpLog.error('doCheck failed with {0}:{1}'.format(errtype.__name__,errvalue))
                            tmpStat = Interaction.SC_FAILED
                    # update
                    if tmpStat != Interaction.SC_SUCCEEDED:
                        tmpLog.error('failed to check assignment')
                    else:
                        tmpRet = self.taskBufferIF.setCloudToTasks_JEDI(taskCloudMap)
                        tmpLog.info('done with {0} for {1}'.format(tmpRet,str(taskCloudMap)))
            except:
                errtype,errvalue = sys.exc_info()[:2]
                logger.error('{0} failed in runImpl() with {1}:{2}'.format(self.__class__.__name__,errtype.__name__,errvalue))



# thread for real worker
class TaskBrokerThread (WorkerThread):

    # constructor
    def __init__(self,taskList,threadPool,taskbufferIF,ddmIF,implFactory,
                 vo,prodSourceLabel,workQueue):
        # initialize woker with no semaphore
        WorkerThread.__init__(self,None,threadPool,logger)
        # attributres
        self.taskList = taskList
        self.taskBufferIF = taskbufferIF
        self.ddmIF = ddmIF.getInterface(vo)
        self.implFactory = implFactory
        self.vo = vo
        self.prodSourceLabel = prodSourceLabel
        self.workQueue = workQueue


    # main
    def runImpl(self):
        while True:
            try:
                # get a part of list
                nTasks = 100
                taskList = self.taskList.get(nTasks)
                # no more datasets
                if len(taskList) == 0:
                    self.logger.debug('{0} terminating since no more items'.format(self.__class__.__name__))
                    return
                # make logger
                tmpLog = MsgWrapper(self.logger)
                tmpLog.info('start')
                tmpStat = Interaction.SC_SUCCEEDED
                # get TaskSpecs
                tmpListToAssign = []
                for tmpTaskItem in taskList:
                    tmpListItem = self.taskBufferIF.getTasksToBeProcessed_JEDI(None,None,None,None,None,simTasks=[tmpTaskItem])
                    if tmpListItem == None:
                        # failed
                        tmpLog.error('failed to get the input chunks for {0}'.format(tmpTaskItem))
                        tmpStat = Interaction.SC_FAILED
                        break
                # get impl                    
                if tmpStat == Interaction.SC_SUCCEEDED:                    
                    tmpLog.info('getting Impl')
                    try:
                        impl = self.implFactory.getImpl(self.vo,self.prodSourceLabel)
                        if impl == None:
                            # task refiner is undefined
                            tmpLog.error('task broker is undefined for vo={0} sourceLabel={1}'.format(self.vo,self.prodSourceLabel))
                            tmpStat = Interaction.SC_FAILED
                    except:
                        errtype,errvalue = sys.exc_info()[:2]
                        tmpLog.error('getImpl failed with {0}:{1}'.format(errtype.__name__,errvalue))
                        tmpStat = Interaction.SC_FAILED
                # brokerage
                if tmpStat == Interaction.SC_SUCCEEDED:
                    tmpLog.info('brokerage with {0}'.format(impl.__class__.__name__))
                    try:
                        tmpStat = impl.doBrokerage(tmpListToAssign,self.vo,
                                                   self.prodSourceLabel,self.workQueue)
                    except:
                        errtype,errvalue = sys.exc_info()[:2]
                        tmpLog.error('doBrokerage failed with {0}:{1}'.format(errtype.__name__,errvalue))
                        tmpStat = Interaction.SC_FAILED
                # register
                if tmpStat != Interaction.SC_SUCCEEDED:
                    tmpLog.error('failed')
                else:
                    tmpLog.info('done')                    
            except:
                errtype,errvalue = sys.exc_info()[:2]
                logger.error('{0} failed in runImpl() with {1}:{2}'.format(self.__class__.__name__,errtype.__name__,errvalue))
        


########## lauch 
                
def launcher(commuChannel,taskBufferIF,ddmIF,vos=None,prodSourceLabels=None):
    p = TaskBroker(commuChannel,taskBufferIF,ddmIF,vos,prodSourceLabels)
    p.start()
