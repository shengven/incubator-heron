/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

package org.apache.heron.healthmgr.common;

import java.net.HttpURLConnection;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.Collection;
import java.util.logging.Logger;

import javax.inject.Inject;
import javax.inject.Named;
import javax.inject.Provider;

import org.apache.heron.api.generated.TopologyAPI;
import org.apache.heron.proto.system.PhysicalPlans.PhysicalPlan;
import org.apache.heron.proto.tmaster.TopologyMaster;
import org.apache.heron.spi.statemgr.SchedulerStateManagerAdaptor;
import org.apache.heron.spi.utils.NetworkUtils;

import static org.apache.heron.healthmgr.HealthPolicyConfig.CONF_TOPOLOGY_NAME;

/**
 * A topology's physical plan may get updated at runtime. This provider is used to
 * fetch the latest version from the tmaster and provide to any dependent components.
 */
public class PhysicalPlanProvider implements Provider<PhysicalPlan> {
  private static final Logger LOG = Logger.getLogger(PhysicalPlanProvider.class.getName());

  private final SchedulerStateManagerAdaptor stateManagerAdaptor;
  private final String topologyName;

  private PhysicalPlan cachedPhysicalPlan = null;

  @Inject
  public PhysicalPlanProvider(SchedulerStateManagerAdaptor stateManagerAdaptor,
                              @Named(CONF_TOPOLOGY_NAME) String topologyName) {
    this.stateManagerAdaptor = stateManagerAdaptor;
    this.topologyName = topologyName;
  }

  @Override
  public synchronized PhysicalPlan get() {
    TopologyMaster.TMasterLocation tMasterLocation
        = stateManagerAdaptor.getTMasterLocation(topologyName);
    String host = tMasterLocation.getHost();
    int port = tMasterLocation.getControllerPort();

    // construct metric cache stat url
    String url = "http://" + host + ":" + port + "/get_current_physical_plan";
    LOG.fine("tmaster physical plan query endpoint: " + url);

    // http communication
    HttpURLConnection con = NetworkUtils.getHttpConnection(url);
    NetworkUtils.sendHttpGetRequest(con);
    byte[] responseData = NetworkUtils.readHttpResponse(con);
    // byte to base64 string
    String encodedString = new String(responseData);
    LOG.fine("tmaster returns physical plan in base64 str: " + encodedString);
    // base64 string to proto bytes
    byte[] decodedBytes = Base64.getDecoder().decode(encodedString);
    // construct proto obj from bytes
    PhysicalPlan physicalPlan = null;
    try {
      physicalPlan = PhysicalPlan.parseFrom(decodedBytes);
    } catch (Exception e) {
      throw new InvalidStateException(topologyName, "Failed to fetch the physical plan");
    }

    cachedPhysicalPlan = physicalPlan;
    return physicalPlan;
  }

  public PhysicalPlan getCachedPhysicalPlan() {
    try {
      get();
    } catch (InvalidStateException e) {
      if (cachedPhysicalPlan == null) {
        throw e;
      }
    }
    return cachedPhysicalPlan;
  }

  /**
   * A utility method to extract bolt component names from the topology.
   *
   * @return array of all bolt names
   */
  protected Collection<String> getBoltNames(PhysicalPlan pp) {
    TopologyAPI.Topology localTopology = pp.getTopology();
    ArrayList<String> boltNames = new ArrayList<>();
    for (TopologyAPI.Bolt bolt : localTopology.getBoltsList()) {
      boltNames.add(bolt.getComp().getName());
    }

    return boltNames;
  }
  public Collection<String> getBoltNames() {
    getCachedPhysicalPlan();
    return getBoltNames(cachedPhysicalPlan);
  }

  /**
   * A utility method to extract spout component names from the topology.
   *
   * @return array of all spout names
   */
  protected Collection<String> getSpoutNames(PhysicalPlan pp) {
    TopologyAPI.Topology localTopology = pp.getTopology();
    ArrayList<String> spoutNames = new ArrayList<>();
    for (TopologyAPI.Spout spout : localTopology.getSpoutsList()) {
      spoutNames.add(spout.getComp().getName());
    }

    return spoutNames;
  }
  public Collection<String> getSpoutNames() {
    getCachedPhysicalPlan();
    return getSpoutNames(cachedPhysicalPlan);
  }

  public Collection<String> getSpoutBoltNames() {
    getCachedPhysicalPlan();
    Collection<String> ret = getBoltNames(cachedPhysicalPlan);
    ret.addAll(getSpoutNames(cachedPhysicalPlan));
    return ret;
  }
}
